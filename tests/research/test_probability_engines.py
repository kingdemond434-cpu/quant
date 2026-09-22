"""The probability engines' arithmetic: a planted miscalibration is measured, a dislocation fires
only above costs + uncertainty + regime buffer, and a forecast is usable only after its
available_time (anti-lookahead)."""
from __future__ import annotations

import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import probability_engines as PE  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _planted(n: int, slope: float, *, seed: int = 7) -> list[tuple[float, float]]:
    """Stated p vs a TRUE probability of sigmoid(slope * logit(p)): slope < 1 is overconfident."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        p = min(0.98, max(0.02, rng.betavariate(2.0, 2.0)))
        true_p = PE.sigmoid(slope * PE.logit(p))
        out.append((p, 1.0 if rng.random() < true_p else 0.0))
    return out


# ------------------------------------------------------------------ the reliability curve
def test_reliability_curve_measures_a_planted_overconfident_engine() -> None:
    table = PE.reliability_curve(_planted(6000, 0.5))
    assert table.status == PE.MEASURED and table.n == 6000
    hi = [b for b in table.bins if b.status == PE.MEASURED and b.mean_p is not None
          and b.mean_p > 0.85]
    assert hi, "the top bins carry enough n to be measured"
    for b in hi:
        assert b.freq is not None and b.freq < b.mean_p - 0.05, \
            "when it says ~90% it happens ~70% of the time"
    assert table.ece is not None and table.ece > 0.05
    assert table.calibrate(0.9) < 0.82, "calibration pulls an overconfident 0.9 towards truth"
    ys = [y for _, y in table.isotonic]
    assert ys == sorted(ys), "the isotonic fit is monotone"
    honest = PE.reliability_curve(_planted(6000, 1.0, seed=3))
    assert honest.ece is not None and honest.ece < 0.04


def test_minimum_n_reads_unmeasured_and_leaves_p_untouched() -> None:
    table = PE.reliability_curve(_planted(40, 0.5))
    assert table.status == PE.UNMEASURED and table.bins == () and table.ece is None
    assert "40 resolved forecasts < 100" in table.why
    assert table.calibrate(0.9) == PE.clip(0.9)
    sparse = PE.reliability_curve(_planted(120, 0.5))
    assert sparse.status == PE.MEASURED
    assert any(b.status == PE.UNMEASURED and b.n < PE.MIN_N_BIN for b in sparse.bins), \
        "a thin bin is UNMEASURED inside a measured table"


def test_curves_by_regime_key_the_record_and_keep_an_overall_table() -> None:
    rec = [PE.Resolved(p=p, y=y, regime="up_hi" if i % 2 else "down_lo", at=T0)
           for i, (p, y) in enumerate(_planted(400, 0.6))]
    tables = PE.curves_by_regime(rec)
    assert set(tables) == {"up_hi", "down_lo", "overall"}
    assert tables["overall"].n == 400 and tables["up_hi"].n == 200


# ------------------------------------------------------------------ the dislocation rule
def _market(seed: int = 1) -> PE.MarketImplied:
    rng = random.Random(seed)
    returns = [rng.gauss(0.0, 0.004) for _ in range(2000)]
    return PE.market_implied(returns, cost=0.0005)


def _calibrated_table() -> PE.CalibrationTable:
    return PE.reliability_curve(_planted(3000, 1.0, seed=11))


def test_dislocation_fires_only_above_costs_uncertainty_and_regime_buffer() -> None:
    market = _market()
    assert market.status == PE.MEASURED and market.p is not None and 0.45 < market.p < 0.55
    assert market.cost_probability is not None and 0.02 < market.cost_probability < 0.2
    ens = PE.Ensemble(p=0.66, uncertainty=0.03, n=2, members={"a": 0.66, "b": 0.66},
                      raw={"a": 0.7, "b": 0.7}, excluded={}, status=PE.MEASURED)
    fired = PE.dislocation(ens, market, costs=0.04, uncertainty=0.03, regime_buffer=0.02)
    assert fired.fired and fired.side == 1 and abs(fired.threshold - 0.09) < 1e-12
    assert fired.edge is not None and fired.edge > 0.09 and "regime buffer" in fired.why
    blocked = PE.dislocation(ens, market, costs=0.04, uncertainty=0.03, regime_buffer=0.10)
    assert not blocked.fired and blocked.side == 0 and "largest term: regime buffer" in blocked.why
    costly = PE.dislocation(ens, market, costs=0.12, uncertainty=0.03, regime_buffer=0.02)
    assert not costly.fired and "largest term: costs" in costly.why
    defaults = PE.dislocation(ens, market, regime_buffer=0.02)
    assert defaults.costs == market.cost_probability and defaults.uncertainty == 0.03
    empty = PE.Ensemble(None, None, 0, {}, {"a": 0.7}, {"a": "no curve"}, PE.UNMEASURED)
    nothing = PE.dislocation(empty, market)
    assert nothing.status == PE.UNMEASURED and not nothing.fired and nothing.edge is None


def test_ensemble_admits_only_calibrated_engines_and_the_buffer_penalises_unmeasured() -> None:
    good = _calibrated_table()
    thin = PE.reliability_curve(_planted(20, 1.0))
    ens = PE.ensemble({"P1": 0.7, "P4": 0.65, "P6": 0.9}, {"P1": good, "P4": good, "P6": thin})
    assert ens.status == PE.MEASURED and set(ens.members) == {"P1", "P4"}
    assert "P6" in ens.excluded and "< 100" in ens.excluded["P6"]
    assert ens.p is not None and 0.6 < ens.p < 0.75
    assert ens.uncertainty is not None and 0.0 < ens.uncertainty < 0.1
    assert PE.regime_buffer(None) == PE.REGIME_BUFFER_BASE + PE.UNMEASURED_REGIME_PENALTY
    assert PE.regime_buffer(good) < PE.regime_buffer(None)
    none = PE.ensemble({"P6": 0.9}, {"P6": thin})
    assert none.status == PE.UNMEASURED and none.n == 0


# ------------------------------------------------------------------ anti-lookahead
def _forecast(at: datetime, available: datetime, p: float) -> PE.ProbabilityForecast:
    return PE.ProbabilityForecast(engine="P6", target="XAUUSD", horizon="1d", at=at,
                                  available_time=available, p=p, regime="up_hi")


def test_a_forecast_is_usable_only_after_its_available_time() -> None:
    later = [_forecast(T0 + timedelta(hours=i), T0 + timedelta(hours=i, days=3), 0.9)
             for i in range(150)]
    rec = PE.resolved_pairs(later, lambda f: 1.0)
    assert rec.withheld_lookahead == 150 and rec.pairs == ()
    assert PE.reliability_curve([(r.p, r.y) for r in rec.pairs]).status == PE.UNMEASURED
    on_time = [_forecast(T0 + timedelta(hours=i), T0 + timedelta(hours=i - 1), 0.9)
               for i in range(150)]
    rec2 = PE.resolved_pairs(on_time, lambda f: 1.0 if f.at.hour % 2 else 0.0)
    assert rec2.withheld_lookahead == 0 and len(rec2.pairs) == 150
    assert not PE.usable(later[0], later[0].at) and PE.usable(on_time[0], on_time[0].at)
    unresolved = PE.resolved_pairs(on_time[:3], lambda f: None)
    assert unresolved.unresolved == 3 and unresolved.pairs == ()


# ------------------------------------------------------------------ consensus, lead, V(a)
def test_consensus_dispersion_anomaly_and_lead() -> None:
    con = PE.consensus({"P1": 0.6, "P4": 0.62, "P6": 0.2})
    assert con.n == 3 and con.dispersion is not None and con.dispersion > 0.15
    assert con.anomalies["P6"] < -2.0 and abs(con.anomalies["P1"]) < 2.0
    assert con.agreement == 2 / 3
    assert PE.consensus({}).status == PE.UNMEASURED
    rng = random.Random(5)
    a = [0.5 + 0.3 * ((i // 7) % 2) + rng.gauss(0, 0.01) for i in range(200)]
    b = [0.0] * 2 + a[:-2]
    ld = PE.lead(a, b, max_lag=4)
    assert ld.status == PE.MEASURED and ld.lag == 2 and ld.leader == "a"
    assert PE.lead(a[:10], b[:10]).status == PE.UNMEASURED
    assert PE.shock(0.5, 0.7) and not PE.shock(0.5, 0.6) and not PE.shock(None, 0.9)


def test_value_of_cell_and_schedule_rank_by_excess_edge_and_disagreement() -> None:
    hot = PE.value_of_cell(edge=0.2, threshold=0.08, dispersion=0.1, n_engines=3)
    cold = PE.value_of_cell(edge=0.05, threshold=0.08, dispersion=0.1, n_engines=3)
    seen = PE.value_of_cell(edge=0.2, threshold=0.08, dispersion=0.1, n_engines=3, novelty=0.25)
    unknown = PE.value_of_cell(edge=None, threshold=None, dispersion=0.2, n_engines=2)
    assert hot > seen > cold > 0 and unknown > 0
    assert PE.schedule({"a": cold, "b": hot, "c": seen}, capacity=2) == ["b", "c"]
    assert PE.schedule({}, capacity=3) == []
