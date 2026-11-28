"""`degree_day_revision`: NOAA CPC degree-day forecast revisions as dated events on XNGUSD.

  0. the family fires on a constructed revision, on the named side, in the named direction;
  1. it refuses BY NAME when the parquet, the product or the column is absent (a TypeError);
  2. it never enters before `available_time` (nor before the broker-offset bar);
  3. a null revision is no event, and never enters any later issue's window;
  4. the z-score reads only prior issues;
  5. the family, its proposer and the hourly leg are wired, and the proposer writes its report,
     parked case included.
All inputs are synthetic; nothing touches the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "scripts"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_degree_day_revision as F  # noqa: E402

_ISSUES = pd.date_range("2025-11-01", "2026-03-31", freq="D", tz="UTC")
_SPIKE = pd.Timestamp("2026-02-10", tz="UTC")


def _bars(n: int = 6000, end: str = "2026-06-30 23:00", seed: int = 5) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = pd.Series(3.0 * np.exp(np.cumsum(rng.normal(0, 0.002, n))), index=idx)
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]), "high": close * 1.002,
                         "low": close * 0.998, "close": close, "tick_volume": 100.0}, index=idx)


def _frame(spike: float = 40.0, after: float = 0.0, lag_h: float = 24.0,
           null_at: tuple[pd.Timestamp, ...] = ()) -> pd.DataFrame:
    """One row per daily issue in the lake's PIT envelope. Bounded noise (a sine never reaches 3
    sigma of its own trailing history); the first issue's revision is null, as the producer
    writes it."""
    rows = []
    for i, it in enumerate(_ISSUES):
        rev: float | None = 3.0 * np.sin(1.3 * i)
        if it == _SPIKE:
            rev = spike
        elif it > _SPIKE:
            rev = float(rev) + after
        if i == 0 or it in null_at:
            rev = None
        rows.append({"available_time": it + pd.Timedelta(hours=lag_h), "event_time": it,
                     "source_id": "noaa_cpc_dd7_gas_hdd",
                     "vintage_id": f"cpc_dd7_gas_hdd@{it.isoformat()}",
                     "retrieval_time": "2026-11-11T00:00:00+00:00",
                     "conus_hdd_rev": rev, "conus_hdd_lvl": 150.0,
                     "conus_hdd_nov": None if rev is None else 6})
    return pd.DataFrame(rows)


@pytest.fixture
def lake(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "SERIES_DIR", tmp_path)
    F._frame.cache_clear()

    def write(df: pd.DataFrame, product: str = "cpc_dd7_gas_hdd") -> Path:
        path = tmp_path / f"noaa_{product}.parquet"
        df.to_parquet(path, index=False)
        F._frame.cache_clear()
        return path
    yield write
    F._frame.cache_clear()


def _sig(**kw):
    p = {"product": "cpc_dd7_gas_hdd", "region": "conus", "measure": "hdd", "move": "up",
         "min_abs": 3.0, "direction": "long", "window": 30, "hold_bars": 24}
    p.update(kw)
    return F.family_degree_day_revision(_bars(), **p)


def test_fires_on_a_constructed_revision_on_the_named_side(lake):
    lake(_frame())
    sig = _sig()
    assert len(sig) == 1 and sig[0].side == 1
    knowable = _SPIKE + pd.Timedelta(hours=24)
    floor = knowable + pd.Timedelta(hours=F.BROKER_MAX_OFFSET_H)
    assert floor <= sig[0].time < floor + pd.Timedelta(hours=2)
    assert sig[0].tag.startswith("degree_day_revision:cpc_dd7_gas_hdd:conus_hdd:up:long")
    # the other side of the revision does not fire; `direction` is the side, `side` is ignored
    assert _sig(move="down") == []
    short = F.family_degree_day_revision(_bars(), side=1, min_abs=3.0, window=30,
                                         direction="short")
    assert len(short) == 1 and short[0].side == -1
    lake(_frame(spike=-40.0))
    down = _sig(move="down", direction="short")
    assert len(down) == 1 and down[0].side == -1
    assert _sig(move="up") == []


def test_refuses_by_name_when_the_parquet_or_column_is_absent(lake, tmp_path):
    with pytest.raises(F.DegreeDayUnavailable, match=F.ABSENT) as exc:
        _sig()
    assert isinstance(exc.value, TypeError) and "noaa_cpc_dd7_gas_hdd.parquet" in str(exc.value)
    lake(_frame())
    with pytest.raises(TypeError, match=F.ABSENT) as exc:
        _sig(measure="cdd")                                  # the HDD product has no CDD column
    assert "conus_cdd_rev" in str(exc.value)
    with pytest.raises(F.DegreeDayUnavailable, match=F.ABSENT):
        _sig(product="cpc_dd7_pop_cdd", measure="cdd")       # no parquet for that product
    with pytest.raises(F.DegreeDayUnavailable, match=F.ABSENT):
        _sig(product="vibes")
    lake(_frame().drop(columns=["available_time"]))
    with pytest.raises(F.DegreeDayUnavailable, match="available_time"):
        _sig()


def test_never_enters_before_available_time(lake):
    for lag in (24.0, 37.5):                         # an issue fetched late is knowable late
        lake(_frame(lag_h=lag))
        sig = _sig()
        knowable = _SPIKE + pd.Timedelta(hours=lag)
        assert sig and all(s.time >= knowable + pd.Timedelta(hours=F.BROKER_MAX_OFFSET_H)
                           for s in sig)
    # a later revision moves nothing that entered before it
    lake(_frame())
    a = _sig()
    lake(_frame(after=500.0))
    b = _sig()
    cut = _SPIKE + pd.Timedelta(hours=24 + F.BROKER_MAX_OFFSET_H + 1)
    assert [s.time for s in a if s.time <= cut] == [s.time for s in b if s.time <= cut]
    # a bare-date stamp carries no hour: it waits for the following UTC day
    df = _frame()
    df["available_time"] = [str(t.date()) for t in df["event_time"]]
    lake(df)
    sig = _sig()
    floor = _SPIKE + pd.Timedelta(days=1, hours=F.BROKER_MAX_OFFSET_H)
    assert sig and sig[0].time >= floor


def test_a_null_revision_is_no_event(lake):
    lake(_frame(null_at=(_SPIKE,)))
    assert _sig() == []
    r = F.revisions("cpc_dd7_gas_hdd", "conus", "hdd")
    assert _SPIKE not in set(r["issue"]) and _ISSUES[0] not in set(r["issue"])
    assert r["rev"].notna().all()
    # a zero revision is not news either, even when it scores far from its window
    df = _frame()
    df.loc[df["event_time"] != _SPIKE, "conus_hdd_rev"] += 50.0
    df.loc[df["event_time"] == _SPIKE, "conus_hdd_rev"] = 0.5   # the same issue, not zero: fires
    lake(df)
    assert len(_sig(move="down", direction="short", min_abs=3.0)) == 1
    df.loc[df["event_time"] == _SPIKE, "conus_hdd_rev"] = 0.0
    lake(df)
    assert _sig(move="down", direction="short", min_abs=3.0) == []


def test_the_z_score_reads_only_prior_issues():
    a = F.prior_z(pd.Series(np.r_[np.sin(np.arange(40.0)), 9.0]), 10)
    b = F.prior_z(pd.Series(np.r_[np.sin(np.arange(40.0)), 1e9]), 10)
    assert a.iloc[:-1].equals(b.iloc[:-1])
    # the first `window` issues have no full prior window: unscored, never zero
    assert a.iloc[:10].isna().all() and a.iloc[10:].notna().all()
    # issue k's own value is outside its window
    s = pd.Series(np.r_[np.ones(10) * 2.0 + np.arange(10) * 0.1, 100.0])
    z = F.prior_z(s, 10)
    prior = s.iloc[:10]
    assert z.iloc[-1] == pytest.approx((100.0 - prior.mean()) / prior.std())


def test_quiet_refusals_on_unknown_recipe_values(lake):
    lake(_frame())
    for kw in ({"region": "atlantis"}, {"measure": "gdd"}, {"move": "both"},
               {"direction": "sideways"}, {"min_abs": -1.0}, {"window": 1}):
        assert _sig(**kw) == []


def test_the_family_and_its_proposer_are_wired():
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES

    from research import axis_registry, hourly_cycle, orthogonal_sweep
    assert ORTHOGONAL_FAMILIES["degree_day_revision"] is F.family_degree_day_revision
    assert "degree_day_revision" in FAMILY_INPUTS
    assert "degree_day_revision" in orthogonal_sweep.NOT_SOURCED_HERE
    assert axis_registry.FAMILY_TABLE["degree_day_revision"][0] == "macro_release"
    assert "degree_day_revision_proposer" in hourly_cycle.LEG_BUDGET_SEC
    assert "degree_day_revision_proposer" in hourly_cycle.LEG_DEPARTMENT
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "research/degree_day_revision_proposer.py" in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["degree_day_revision_proposer"] == "prediction"
    assert "desks/mt5/mt5desk/family_degree_day_revision.py" in (
        ROOT / "ops" / "money_closure.txt").read_text("utf-8").split()
    from libs.ops.capability_graph import NODES
    assert any(n.name == "degree_day_revision_proposer" for n in NODES)


def test_the_proposer_charges_its_grid_parks_by_name_and_writes_its_report(lake, tmp_path,
                                                                           monkeypatch):
    from research import degree_day_revision_proposer as P
    from research import proposer_common as pc
    lake(_frame())                                   # gas HDD present; the other three absent
    monkeypatch.setattr(P, "REPORT", tmp_path / "DEGREE_DAY_REVISION_PROPOSER.json")
    monkeypatch.setattr(P, "MIN_BARS", 500)
    monkeypatch.setattr(P, "WINDOWS", (30,))
    monkeypatch.setattr(P, "MIN_ABS", 3.0)
    meta = {"XNGUSD": {"asset_class": "Commodities", "currency_profit": "USD"}}
    monkeypatch.setattr(pc, "universe_meta", lambda: meta)
    monkeypatch.setattr(pc, "bars", lambda s: _bars() if s == "XNGUSD" else None)
    monkeypatch.setattr(pc, "cost_frac", lambda s, m, c: 0.0001)
    from research import universe_policy as up
    monkeypatch.setattr(up, "may_hypothesise", lambda s, family=None: True)
    # the real screen needs 30 trades; a stand-in exercises the charge and the ranking
    monkeypatch.setattr(pc, "screen", lambda d, sig, cost, unf: (
        {"t_gross": 9.0, "clears_cost": True, "n_independent": 40} if sig else None))
    rep = P.run(budget_s=120, donate=False)
    doc = json.loads(P.REPORT.read_text("utf-8"))
    assert doc["status"] == rep["status"] == "OK"
    assert doc["products"]["cpc_dd7_gas_hdd"]["symbols"] == ["XNGUSD"]
    for p in ("cpc_dd7_elec_hdd", "cpc_dd7_pop_hdd", "cpc_dd7_pop_cdd"):
        assert doc["products"][p]["parked_reason"] == F.ABSENT
    # one product reached: 2 (move, direction) x 1 window x 2 holds = 4 variants, all charged;
    # only the up/long pair fires (2 holds), and both screened rows carry the whole grid's charge
    assert doc["tests_run"] == 4 and doc["variants_screened"] == 2
    assert doc["proposals"] and all(r["n_tests_sweep"] == 4 for r in doc["proposals"])
    assert doc["proposals"][0]["params"]["direction"] == "long"
    # everything parked: UNMEASURED, never zero
    (tmp_path / "noaa_cpc_dd7_gas_hdd.parquet").unlink()
    F._frame.cache_clear()
    rep = P.run(budget_s=30, donate=False)
    assert rep["status"] == "UNMEASURED" and rep["tests_run"] == "UNMEASURED"
    assert all(v["parked_reason"] == F.ABSENT for v in rep["products"].values())
    assert json.loads(P.REPORT.read_text("utf-8"))["status"] == "UNMEASURED"
