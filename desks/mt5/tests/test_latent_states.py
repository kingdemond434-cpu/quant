"""latent_states (ROMAN-0839, 0840, 0841) on SIMULATED state-space data only.

Planted world: a common dollar factor drives six USD crosses (each with a mean-reverting
idiosyncratic part), gold = macro fair value (real yield, dollar factor) + a mean-reverting
residual, and CPI prints = latent inflation + noise with breakevens tracking the same state.
Null world: gold, the pairs' idiosyncratic parts and the CPI prints are random walks, where the
random-walk / ungated baselines are optimal."""
from __future__ import annotations

import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import latent_states as ls  # noqa: E402

N_DAYS = 1100
TRAIN = 450
#: ~29 monthly prints follow the training window in 1100 days; the engine's 60 is for the box.
CPI_MIN_N = 24


def _jumps(rng: np.random.Generator, n: int, size: float) -> np.ndarray:
    """Rare dislocations (8% of days, +/- size): the residual a |z| gate should isolate."""
    return np.asarray((rng.uniform(size=n) < 0.08) * rng.choice([-1.0, 1.0], n) * size)


def _world(planted: bool, seed: int = 0) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    days = [d.date() for d in pd.bdate_range("2015-01-05", periods=N_DAYS)]
    n = len(days)
    f = np.cumsum(rng.normal(0, 0.004, n))
    closes: dict[str, list[tuple[str, float]]] = {}
    loads = {"EURUSD": 1.0, "GBPUSD": 0.8, "AUDUSD": 0.9, "USDJPY": 0.7, "USDCAD": 0.6,
             "USDCHF": 0.9}
    for pair, lam in loads.items():
        if planted:
            u = np.zeros(n)
            e = rng.normal(0, 0.001, n) + _jumps(rng, n, 0.01)
            for i in range(1, n):
                u[i] = 0.5 * u[i - 1] + e[i]
        else:
            u = np.cumsum(rng.normal(0, 0.002, n))
        aligned = lam * f + u
        logp = ls.USD_PAIRS[pair] * aligned
        closes[pair] = [(d.isoformat(), float(math.exp(v))) for d, v in zip(days, logp,
                                                                            strict=True)]
    # FRED daily series, dated by calendar day (knowable the next day 09:00 ET)
    dfii = 1.0 + np.cumsum(rng.normal(0, 0.03, n))
    pi = np.cumsum(rng.normal(0, 0.02, n))
    be10 = 2.0 + 0.5 * pi + rng.normal(0, 0.02, n)
    be5 = 2.1 + 0.6 * pi + rng.normal(0, 0.02, n)
    if not planted:
        be10 = 2.0 + np.cumsum(rng.normal(0, 0.02, n))
        be5 = 2.1 + np.cumsum(rng.normal(0, 0.02, n))
    series = {"DFII10": [(d.isoformat(), float(v)) for d, v in zip(days, dfii, strict=True)],
              "T10YIE": [(d.isoformat(), float(v)) for d, v in zip(days, be10, strict=True)],
              "T5YIE": [(d.isoformat(), float(v)) for d, v in zip(days, be5, strict=True)]}
    # gold on the A_d clock: the regressors the desk holds at A_d are day d-1's FRED values
    clock = [ls.avail(d) for d in days]
    dfii_asof = ls.asof(ls.fred_daily(series, "DFII10"), clock)
    dfii_asof = np.where(np.isfinite(dfii_asof), dfii_asof, 1.0)
    if planted:
        s = np.zeros(n)
        e = rng.normal(0, 0.002, n) + _jumps(rng, n, 0.03)
        for i in range(1, n):
            s[i] = 0.5 * s[i - 1] + e[i]
        lg = 7.0 - 0.1 * dfii_asof - 1.0 * f + s
    else:
        lg = 7.0 + np.cumsum(rng.normal(0, 0.01, n))
    closes["XAUUSD"] = [(d.isoformat(), float(math.exp(v))) for d, v in zip(days, lg,
                                                                           strict=True)]
    # monthly CPI prints, released the 12th at 13:30 UTC
    rows = []
    level = 2.5
    for m in range(N_DAYS * 7 // 5 // 30):
        at = datetime(2015 + (m + 1) // 12, (m + 1) % 12 + 1, 12, 13, 30, tzinfo=UTC)
        i = min(n - 1, int(np.searchsorted([c.timestamp() for c in clock], at.timestamp())))
        if planted:
            val = 2.5 + 40 * pi[i] + rng.normal(0, 0.5)
        else:
            level += rng.normal(0, 0.5)
            val = level
        rows.append((at, float(val)))
    prints = {"cpi": {"rows": rows, "basis": "calendar", "source": "synthetic"}}
    now = ls.avail(days[-1]) + timedelta(hours=1)
    return {"closes": closes, "series": series, "prints": prints, "now": now, "f": f,
            "days": days}


@pytest.fixture(scope="module")
def planted() -> dict[str, Any]:
    w = _world(True)
    return {"w": w, "rep": ls.build(w["now"], closes=w["closes"], series=w["series"],
                                    prints=w["prints"], train=TRAIN,
                                    cpi_min_n=CPI_MIN_N)}


@pytest.fixture(scope="module")
def null() -> dict[str, Any]:
    w = _world(False, seed=1)
    return {"w": w, "rep": ls.build(w["now"], closes=w["closes"], series=w["series"],
                                    prints=w["prints"], train=TRAIN,
                                    cpi_min_n=CPI_MIN_N)}


def _c(rep: dict[str, Any], label_start: str) -> list[dict[str, Any]]:
    return [c for c in rep["contracts"] if str(c.get("label", "")).startswith(label_start)]


def test_dollar_factor_is_recovered(planted: dict[str, Any]) -> None:
    rows = planted["rep"]["series"][ls.S_USD]
    est = np.asarray([r["dollar_state"] for r in rows])
    true = planted["w"]["f"][-len(est):]
    corr = np.corrcoef(np.diff(est[100:]), np.diff(true[100:]))[0, 1]
    assert corr > 0.9


def test_planted_effects_are_gain(planted: dict[str, Any]) -> None:
    rep = planted["rep"]
    assert _c(rep, "XAUUSD:gold_resid")[0]["verdict"] == "GAIN"
    assert _c(rep, "XAUUSD:next_week")[0]["verdict"] == "GAIN"
    assert _c(rep, "US:cpi")[0]["verdict"] == "GAIN"
    usd = [c["verdict"] for c in rep["contracts"] if c["cards"] == ["ROMAN-0840"]]
    assert len(usd) == 6 and "GAIN" in usd


def test_null_world_is_not_gain(null: dict[str, Any]) -> None:
    rep = null["rep"]
    for c in rep["contracts"]:
        if c["cards"] != ["ROMAN-0840"]:
            assert c["verdict"] in ("NO_GAIN", "UNMEASURED"), c["label"]
    # six pair contracts at alpha 0.05 each: one false GAIN is chance, two is a broken null
    usd = [c["verdict"] for c in rep["contracts"] if c["cards"] == ["ROMAN-0840"]]
    assert len(usd) == 6 and usd.count("GAIN") <= 1


def test_rows_are_point_in_time(planted: dict[str, Any]) -> None:
    rep = planted["rep"]
    for sid in (ls.S_INFL, ls.S_USD, ls.S_GOLD):
        rows = rep["series"][sid]
        assert rows
        for r in rows[:50] + rows[-50:]:
            at = datetime.fromisoformat(r["available_time"])
            ev = date.fromisoformat(r["event_time"])
            assert at == datetime(ev.year, ev.month, ev.day, tzinfo=UTC) + timedelta(hours=25)


def test_filtered_values_do_not_see_the_future(planted: dict[str, Any]) -> None:
    w, full = planted["w"], planted["rep"]
    cut = w["days"][900]
    closes = {k: [r for r in v if r[0] <= cut.isoformat()] for k, v in w["closes"].items()}
    series = {k: [r for r in v if r[0] <= cut.isoformat()] for k, v in w["series"].items()}
    prints = {"cpi": {**w["prints"]["cpi"], "rows": [r for r in w["prints"]["cpi"]["rows"]
                                                     if r[0] <= ls.avail(cut)]}}
    part = ls.build(ls.avail(cut), closes=closes, series=series, prints=prints, train=TRAIN)
    for sid, col in ((ls.S_GOLD, "gold_fair_value"), (ls.S_USD, "dollar_state"),
                     (ls.S_INFL, "infl_state")):
        a = {r["available_time"]: r[col] for r in full["series"][sid]}
        b = {r["available_time"]: r[col] for r in part["series"][sid]}
        common = sorted(set(a) & set(b))
        assert len(common) > 400
        np.testing.assert_allclose([a[k] for k in common], [b[k] for k in common], rtol=1e-7)


def test_short_history_is_unmeasured() -> None:
    w = _world(True)
    closes = {k: v[:300] for k, v in w["closes"].items()}
    rep = ls.build(w["now"], closes=closes, series=w["series"], prints=w["prints"], train=TRAIN)
    assert rep["status"] == "UNMEASURED"
    assert rep["contracts"] and all(c["verdict"] == "UNMEASURED" for c in rep["contracts"])


def test_ledger_rows_carry_a_basis(planted: dict[str, Any]) -> None:
    obs = ls.ledger_observations(planted["rep"], datetime(2030, 1, 1, tzinfo=UTC))
    from libs.research import sensor_contract as sc
    assert obs
    for o in obs:
        assert o.knowable_basis == "declared_lag"
        assert sc.defects(o) == []
