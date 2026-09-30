"""The analyst-view schema, the point-in-time store, the tracker and the admission contract.

EVERYTHING HERE IS SYNTHETIC OR HAND-WRITTEN AND NOTHING TOUCHES THE NETWORK. The load-bearing
tests:

* `test_a_jump_between_publication_and_first_sighting_is_never_credited` -- the tracker starts
  every return at the first close known after `first_seen_at`, so a move that happened while the
  view was public but not yet held by this desk is not counted as the view's drift.
* `test_a_planted_drift_is_admitted_and_a_null_is_not` -- the placebo contract admits a source
  whose events carry a real post-publication drift, and refuses the same machinery on a null.
* `test_absence_is_unmeasured_never_zero` -- a missing target is None and listed, never 0%.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from libs.research import analyst_views as av

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _view(**kw: object) -> av.AnalystView:
    base: dict[str, object] = {"source": "yahoo_upgrades", "published_at": T0.isoformat(),
                               "published_precision": "datetime", "issuer": "NVDA",
                               "title": "t", "instrument": "NVIDIA", "broker": "MS"}
    base.update(kw)
    return av.AnalystView(**base).finish()  # type: ignore[arg-type]


# ------------------------------------------------------------------------------ schema
@pytest.mark.parametrize(("raw", "score"), [
    ("Strong Buy", 5), ("Overweight", 4), ("Equal-Weight", 3), ("Underweight", 2),
    ("Sell", 1), ("Market Perform", 3), ("Sector Outperform", 4), ("买入", 5), ("增持", 4),
    ("中性", 3), ("减持", 2), ("매수", 4), ("중립", 3), ("비중축소", 2), ("Not Rated", None),
    ("", None), (None, None)])
def test_ratings_normalise_to_the_five_point_scale(raw: object, score: int | None) -> None:
    assert av.normalise_rating(raw) == score


def test_absence_is_unmeasured_never_zero() -> None:
    v = _view(action="reiterate", rating_old_raw="Buy", rating_new_raw="Buy",
              target_old=0, target_new=175.0)
    assert v.target_old is None and v.target_change_pct is None
    assert {"target_old", "target_change_pct"} <= set(v.unmeasured)
    assert v.direction == 0 and v.conviction is None


def test_direction_rules() -> None:
    assert _view(action="up").direction == 1
    assert _view(action="down").direction == -1
    assert _view(action="init", rating_new_raw="Buy").direction == 1
    assert _view(action="init", rating_new_raw="Hold").direction == 0
    assert _view(action="reiterate", target_old=100, target_new=110).direction == 1
    assert _view(action="reiterate", target_old=100, target_new=102).direction == 0
    up = _view(rating_old_raw="Hold", rating_new_raw="Buy")
    assert up.action == "up" and up.direction == 1 and up.conviction == 0.5


def test_event_id_is_stable_and_content_addressed() -> None:
    a = _view(native_id="x|1")
    b = _view(native_id="x|1", title="other")
    c = _view(native_id="x|2")
    assert a.event_id == b.event_id != c.event_id


# ------------------------------------------------------------------------------ the store
def test_store_stamps_keeps_first_seen_and_chains_revisions(tmp_path: Path) -> None:
    store = av.AnalystViewStore(tmp_path / "s.jsonl")
    t1 = T0 + timedelta(hours=2)
    got = store.append([_view(native_id="n1", action="up")], now=t1)
    assert got["added"] == 1
    row = store.rows()[0]
    for k in ("available_time", "ingested_time", "source_version", "payload_hash"):
        assert row.get(k), k
    assert row["first_seen_at"] == row["available_time"] == t1.isoformat(timespec="seconds")
    # same content again: nothing appended
    assert store.append([_view(native_id="n1", action="up")], now=t1 + timedelta(hours=1)
                        )["unchanged"] == 1
    # changed content: a revision chained to the original, first_seen_at unmoved
    t3 = t1 + timedelta(hours=5)
    rev = store.append([_view(native_id="n1", action="up", target_new=150, target_old=100)],
                       now=t3)
    assert rev["revised"] == 1
    rows = store.rows()
    assert len(rows) == 2
    assert rows[1]["revision_of"] == rows[0]["payload_hash"]
    assert rows[1]["first_seen_at"] == rows[0]["first_seen_at"]
    assert rows[1]["available_time"] >= t3.isoformat(timespec="seconds")
    assert list(store.first_rows()) == [rows[0]["event_id"]]


def test_fill_prior_reads_the_same_brokers_earlier_view(tmp_path: Path) -> None:
    hist = [{"source": "naver_research", "issuer": "000660", "broker": "KIS",
             "published_at": T0.isoformat(), "target_new": 200000.0, "rating_new": 4,
             "rating_new_raw": "매수"}]
    later = av.AnalystView(source="naver_research", published_at=(T0 + timedelta(days=5)
                                                                  ).isoformat(),
                           issuer="000660", broker="KIS", title="t", rating_new_raw="매수",
                           target_new=260000.0).finish()
    assert later.direction == 0
    assert av.fill_prior([later], hist) == 1
    later.finish()
    assert later.target_old == 200000.0 and later.target_change_pct == 30.0
    assert later.action == "reiterate" and later.direction == 1 and later.prior_from_store


# ------------------------------------------------------------------------------ PIT
def _row(first_seen: datetime, published: datetime, precision: str = "datetime",
         direction: int = 1, eid: str = "e1", target: str = "NVIDIA") -> dict[str, object]:
    return {"event_id": eid, "source": "yahoo_upgrades", "instrument": target, "leads": [],
            "direction": direction, "broker": "MS", "published_at": published.isoformat(),
            "published_precision": precision, "first_seen_at": first_seen.isoformat(),
            "available_time": first_seen.isoformat()}


def test_knowable_is_first_seen_and_backfill_is_never_an_observation() -> None:
    pub = T0
    live = _row(pub + timedelta(hours=6), pub)
    assert av.knowable_at(live) == (pub + timedelta(hours=6), "LIVE")
    date_only = _row(pub + timedelta(hours=1), pub, precision="date")
    assert av.knowable_at(date_only)[0] == pub + av.DATE_PRECISION_LAG
    stale = _row(pub + timedelta(days=30), pub, eid="e2")
    assert av.knowable_at(stale) == (None, "BACKFILL")
    obs, census = av.observations([live, stale])
    assert len(obs) == 1 and census.get("backfill") == 1
    vend, _ = av.observations([live, stale], basis="vendor_dated")
    assert len(vend) == 2


def test_a_directionless_first_sighting_is_floored_at_its_revision() -> None:
    first = _row(T0 + timedelta(hours=1), T0, direction=0)
    rev = {**first, "direction": 1, "available_time": (T0 + timedelta(hours=30)).isoformat(),
           "revision_of": "abc"}
    obs, _ = av.observations([first, rev])
    assert len(obs) == 1 and obs[0].at == T0 + timedelta(hours=30)


def _h1(days: int, price: dict[int, float], start: datetime = T0) -> pd.DataFrame:
    """8 bars a day, 13:00-20:00 UTC; the close on day d is `price` at the latest key <= d."""
    idx, closes = [], []
    keys = sorted(price)
    for d in range(days):
        for h in range(13, 21):
            idx.append(start + timedelta(days=d, hours=h))
            p = price[max(k for k in keys if k <= d)]
            closes.append(p)
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c},
                        index=pd.DatetimeIndex(idx))


def test_a_jump_between_publication_and_first_sighting_is_never_credited() -> None:
    bars = {"NVIDIA": av.to_daily(_h1(20, {0: 100.0, 10: 110.0, 11: 121.0}))}
    published = T0 + timedelta(days=10, hours=12)
    first_seen = T0 + timedelta(days=11, hours=2)            # held only the next morning
    obs, _ = av.observations([_row(first_seen, published)])
    rows, census = av.track(av.daily_net(obs), bars)
    assert not census
    r = rows[0]
    assert r["entry_date"] == str((T0 + timedelta(days=11)).date())
    assert r["car_1d"] == pytest.approx(0.0)                   # day 11 close -> day 12 close
    # the lookahead version would have credited log(121/110) to the view
    assert abs(r["car_1d"] - math.log(121 / 110)) > 0.05


def test_benchmark_is_subtracted_when_held() -> None:
    bars = {"NVIDIA": av.to_daily(_h1(10, {0: 100.0, 3: 110.0})),
            "US500": av.to_daily(_h1(10, {0: 100.0, 3: 105.0}))}
    obs, _ = av.observations([_row(T0 + timedelta(days=2, hours=1), T0 + timedelta(days=2))])
    rows, _ = av.track(av.daily_net(obs), bars, bench={"NVIDIA": "US500"})
    assert rows[0]["benchmark"] == "US500"
    assert rows[0]["car_1d"] == pytest.approx(math.log(110 / 100) - math.log(105 / 100))


# ------------------------------------------------------------------------------ contract
def _synthetic(n_days: int, n_events: int, drift: float, seed: int,
               targets: tuple[str, ...] = ("A", "B", "C")
               ) -> tuple[list[av.Observation], dict[str, av.DailyBars | None]]:
    rng = np.random.default_rng(seed)
    bars: dict[str, av.DailyBars | None] = {}
    obs: list[av.Observation] = []
    for k, t in enumerate(targets):
        rets = rng.normal(0.0, 0.01, n_days)
        pos = rng.choice(np.arange(40, n_days - 40), size=n_events, replace=False)
        dirs = rng.choice([-1, 1], size=n_events)
        for p, d in zip(pos, dirs, strict=True):
            rets[p + 1: p + 6] += d * drift
            obs.append(av.Observation(t, "direct", "", "src", "b",
                                      T0 + timedelta(days=int(p), hours=12), int(d)))
        close = 100 * np.exp(np.cumsum(rets))
        dates = np.asarray([np.datetime64((T0 + timedelta(days=i)).date()) for i in
                            range(n_days)], dtype="datetime64[D]")
        known = np.asarray([(T0 + timedelta(days=i, hours=23)).timestamp()
                            for i in range(n_days)])
        bars[t] = av.DailyBars(dates=dates, close=close, known=known)
        assert k >= 0
    return obs, bars


def test_a_planted_drift_is_admitted_and_a_null_is_not() -> None:
    obs, bars = _synthetic(900, 25, 0.004, seed=7)
    got = av.placebo_contract(obs, bars, n_placebo=200, seed=1)["src"]
    assert got["status"] == "ADMIT", got
    assert got["t"] > 3 and got["p_placebo"] <= 0.05
    obs0, bars0 = _synthetic(900, 25, 0.0, seed=11)
    null = av.placebo_contract(obs0, bars0, n_placebo=200, seed=1)["src"]
    assert null["status"] == "REJECT", null
    assert abs(null["placebo_t_mean"]) < 1.0


def test_a_thin_source_is_unmeasured_not_passed() -> None:
    obs, bars = _synthetic(300, 3, 0.01, seed=3)
    got = av.placebo_contract(obs, bars)["src"]
    assert got["status"] == av.UNMEASURED and got["n"] < av.MIN_EVENTS


def test_aggregate_and_axis_rows() -> None:
    obs, bars = _synthetic(400, 15, 0.004, seed=5)
    rows, _ = av.track(obs, bars)
    agg = av.aggregate(rows, ("source",))
    assert agg[0]["5d"]["status"] == "MEASURED" and agg[0]["5d"]["t"] > 0
    stored = [{"event_id": f"e{i}", "source": "s", "instrument": "NVIDIA", "leads": ["kr_semis"],
               "direction": d, "published_at": T0.isoformat(),
               "published_precision": "datetime",
               "first_seen_at": (T0 + timedelta(hours=i)).isoformat()}
              for i, d in enumerate((1, 1, -1))]
    days = av.rows_by_day(stored, universe={"NVIDIA", "USDKRW", "AMD"})
    nv = [d for d in days if d["symbol"] == "NVIDIA"]
    assert nv and nv[0]["n_views"] == 3 and nv[0]["net_breadth"] == pytest.approx(1 / 3, abs=1e-3)
    assert {d["symbol"] for d in days} == {"NVIDIA", "USDKRW", "AMD"}
    json.dumps(days)
