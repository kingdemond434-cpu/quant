"""THE OPTIONS-IMPLIED LANE, ON FIXTURES: the features' point-in-time stamps, no lookahead in
the features or the families, the cells' cluster, and the wiring onto the box's hourly clock.

No test touches the network. The CBOE source is `vol_archive.FakeVolSource`; every path the
producer writes is pointed into `tmp_path`, so nothing lands in the desk's own data or reports.
Live yield (what the box's CBOE fetch returns, and how many cells it mints) is UNMEASURED here.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import options_implied as P  # noqa: E402
from mt5desk import family_implied_vol as F  # noqa: E402
from recorders import vol_archive as va  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
REGISTRY = {"XAUUSD": {}, "US500": {}, "EURUSD": {}, "XTIUSD": {}}


def _days(n: int, end: str = "2026-10-02") -> list[str]:
    return [d.date().isoformat() for d in pd.bdate_range(end=end, periods=n)]


def _walk(n: int, level: float, seed: int, scale: float = 0.6) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(np.maximum(5.0, level + np.cumsum(rng.normal(0, scale, n))))


def _source(n: int = 600) -> va.FakeVolSource:
    days = _days(n)
    data = {t: dict(zip(days, _walk(n, lvl, i), strict=True)) for i, (t, lvl) in enumerate(
        [("^GVZ", 18.0), ("^VIX", 16.0), ("^VIX9D", 15.0), ("^VIX3M", 18.0), ("^VIX6M", 20.0),
         ("^EVZ", 7.0), ("^OVX", 35.0)])}
    return va.FakeVolSource(data, missing={"^VXN", "^VXD"})


def _bars(universe: Path, symbol: str, days: int = 900, seed: int = 5) -> pd.DataFrame:
    universe.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end="2026-10-03", periods=days * 24, freq="h", tz="UTC")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01 / np.sqrt(24), len(idx))))
    df = pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                       "close": close}, index=idx)
    df.to_parquet(universe / f"{symbol}_H1.parquet")
    return df


# ------------------------------------------------------------------ the clock ----
def test_a_close_is_knowable_only_after_publication_plus_the_world_models_pad() -> None:
    from research import world_model as wm

    assert P.CLOCK_PAD_H == wm.CLOCK_PAD_H
    pub, avail = P.knowable_at("2026-10-02")
    assert pub == "2026-10-03T00:00:00+00:00"
    assert avail == "2026-10-03T04:00:00+00:00"
    # The CBOE close prints 16:15 ET = 21:15 UTC at the latest; the stamp is hours after it.
    assert pd.Timestamp(avail) - pd.Timestamp("2026-10-02T21:15:00+00:00") \
        >= pd.Timedelta(hours=6)


def test_every_feature_row_carries_its_pit_envelope_and_vintage() -> None:
    iv = dict(zip(_days(300), _walk(300, 18.0, 1), strict=True))
    desk_dates = set(list(iv)[-5:])
    f = P.build_features(iv, desk_dates=desk_dates, ticker="^GVZ", symbol="XAUUSD")
    for col in ("value_date", "event_time", "published_time", "available_time", "vintage",
                "source_id"):
        assert f[col].notna().all(), col
    avail = pd.to_datetime(f["available_time"], utc=True)
    vd = pd.to_datetime(f["value_date"], utc=True)
    assert ((avail - vd) >= pd.Timedelta(hours=24 + P.CLOCK_PAD_H)).all()
    assert list(f["vintage"].tail(5)) == ["desk"] * 5
    assert set(f["vintage"].head(len(f) - 5)) == {"reference"}


# ------------------------------------------------------------------ no lookahead ----
def test_no_feature_on_or_before_a_date_changes_when_the_future_changes(tmp_path) -> None:
    n = 400
    days = _days(n)
    iv = dict(zip(days, _walk(n, 18.0, 2), strict=True))
    term = {t: dict(zip(days, _walk(n, lvl, 10 + i), strict=True))
            for i, (t, lvl) in enumerate([("^VIX9D", 15.0), ("^VIX", 16.0), ("^VIX3M", 18.0),
                                          ("^VIX6M", 20.0)])}
    rv = pd.Series(_walk(n, 14.0, 3), index=days)
    clean = P.build_features(iv, term=term, rv=rv)
    cut = 300
    dirty_iv = {d: (v * 3.0 if i >= cut else v) for i, (d, v) in enumerate(iv.items())}
    dirty_term = {t: {d: (v + 9.0 if i >= cut else v) for i, (d, v) in enumerate(s.items())}
                  for t, s in term.items()}
    dirty_rv = rv.copy()
    dirty_rv.iloc[cut:] = 99.0
    dirty = P.build_features(dirty_iv, term=dirty_term, rv=dirty_rv)
    cols = [c for c in F.FEATURES if c in clean.columns]
    pd.testing.assert_frame_equal(clean.loc[:cut - 1, cols], dirty.loc[:cut - 1, cols])
    assert not clean.loc[cut:, "iv_level"].equals(dirty.loc[cut:, "iv_level"])


def test_realised_vol_for_a_date_uses_no_later_bar(tmp_path) -> None:
    uni = tmp_path / "universe"
    df = _bars(uni, "XAUUSD", days=120)
    clean = P.realised_daily("XAUUSD", uni)
    cut = pd.Timestamp("2026-09-01", tz="UTC")
    df.loc[df.index >= cut, "close"] *= np.exp(np.linspace(0, 2.0, int((df.index >= cut).sum())))
    df.to_parquet(uni / "XAUUSD_H1.parquet")
    dirty = P.realised_daily("XAUUSD", uni)
    assert clean is not None and dirty is not None
    before = [d for d in clean.index if d < "2026-09-01"]
    assert len(before) > 30
    pd.testing.assert_series_equal(clean[before], dirty[before])


def test_features_have_the_meaning_their_names_claim() -> None:
    days = _days(300)
    iv = dict(zip(days, [10.0 + i * 0.05 for i in range(300)], strict=True))   # rising
    term = {"^VIX": iv, "^VIX3M": {d: v - 1.0 for d, v in iv.items()},           # 30D > 3M
            "^VIX9D": {d: v + 1.0 for d, v in iv.items()}}
    rv = pd.Series([8.0] * 300, index=days)
    f = P.build_features(iv, term=term, rv=rv)
    assert f["iv_pct_1y"].iloc[:P.MIN_YEAR - 1].isna().all()     # too short to rank: unmeasured
    assert f["iv_pct_1y"].iloc[-1] == pytest.approx(1.0)          # a new high ranks at the top
    assert f["term_inverted"].iloc[-1] == 1.0
    assert f["slope_9d_30d"].iloc[-1] < 0                         # 9D above 30D: backwardation
    assert f["slope_30d_3m"].iloc[-1] < 0                         # 30D above 3M: backwardation
    assert f["slope_3m_6m"].isna().all()                          # no 6M tenor: UNMEASURED
    fred_only = P.build_features(iv, term={k: term[k] for k in ("^VIX", "^VIX3M")}, rv=rv)
    assert fred_only["slope_9d_30d"].isna().all()                 # never filled from 30D->3M
    assert fred_only["slope_30d_3m"].notna().all()
    assert f["vrp"].iloc[-1] == pytest.approx(f["iv_level"].iloc[-1] - 8.0)
    assert f["iv_chg_5d"].iloc[-1] == pytest.approx(0.25)


# ------------------------------------------------------------------ the history ----
def test_reference_history_fresh_cache_fetch_stale_and_unmeasured(tmp_path) -> None:
    src = va.FakeVolSource({"^GVZ": {"2026-10-01": 18.0, "2026-10-02": 19.0}})
    got, prov = P.reference_history("^GVZ", src, cache_dir=tmp_path, now=NOW)
    assert prov["status"] == "FETCHED" and got["2026-10-02"] == 19.0
    again, prov2 = P.reference_history("^GVZ", None, cache_dir=tmp_path, now=NOW)
    assert prov2["status"] == "CACHE_FRESH" and again == got
    later = NOW.replace(day=7)
    stale, prov3 = P.reference_history("^GVZ", va.FakeVolSource(missing={"^GVZ"}),
                                       cache_dir=tmp_path, now=later)
    assert prov3["status"] == "CACHE_STALE" and stale == got
    none, prov4 = P.reference_history("^OVX", None, cache_dir=tmp_path, now=NOW)
    assert none == {} and prov4["status"] == "UNMEASURED" and prov4["why"]


def test_the_desks_own_vintage_overrides_the_restated_reference() -> None:
    ok = {"source_admitted": True}
    rows = [{"observed_at": "2026-10-02T21:40:00+00:00", "value_date": "2026-10-02",
             "vol_ticker": "^VIX", "implied_vol": 16.4, "term": {"^VIX9D": 15.1}, **ok},
            {"observed_at": "2026-10-02T22:40:00+00:00", "value_date": "2026-10-02",
             "vol_ticker": "^VIX", "implied_vol": 16.5, "term": {}, **ok},
            {"observed_at": "2026-10-03T00:40:00+00:00", "value_date": "",
             "vol_ticker": "^GVZ", "implied_vol": None, **ok},
            # A row from before the route stamp (an unadmitted source) is never a vintage.
            {"observed_at": "2026-10-03T01:40:00+00:00", "value_date": "2026-10-03",
             "vol_ticker": "^OVX", "implied_vol": 40.0, "term": {}}]
    v = P.desk_vintages(rows)
    assert v["^VIX"] == {"2026-10-02": 16.5}            # the newest read of a date wins
    assert v["^VIX9D"] == {"2026-10-02": 15.1}
    assert "^GVZ" not in v                               # an absence is not a value
    assert "^OVX" not in v                               # no admitted route, no vintage


def test_a_held_source_is_never_asked_and_an_unadmitted_cache_is_never_served(tmp_path) -> None:
    asked: list[str] = []
    held = va.FredVolSource(fetch=lambda u, t: asked.append(u) or "")
    got, prov = P.reference_history("^GVZ", held, cache_dir=tmp_path, now=NOW)
    assert got == {} and prov["status"] == "HELD_PENDING_TERMS" and asked == []
    (tmp_path / "GVZ.json").write_text(json.dumps(
        {"ticker": "^GVZ", "fetched_at": NOW.isoformat(), "series": {"2026-10-02": 19.0}}))
    got2, prov2 = P.reference_history("^GVZ", None, cache_dir=tmp_path, now=NOW)
    assert got2 == {} and prov2["status"] == "UNMEASURED"


# ------------------------------------------------------------------ the families ----
def _write_series(root: Path, name: str, avail: list[str], values: list[float]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"available_time": avail, "iv_pct_1y": values}).to_parquet(
        root / f"{name}.parquet")


def test_the_family_holds_a_utc_stamp_back_by_the_broker_offset(tmp_path) -> None:
    avail = [t.isoformat() for t in pd.date_range("2026-01-01 04:00", periods=80, freq="D",
                                                  tz="UTC")]
    vals = [0.5] * 79 + [0.95]
    _write_series(tmp_path, "oi_T", avail, vals)
    stamp = pd.Timestamp(avail[-1])
    idx = pd.DatetimeIndex([stamp + pd.Timedelta(hours=h) for h in (0, 2, 3, 4)])
    mask = F.state_mask("oi_T", "iv_pct_1y", "ge", 0.8, idx, root=tmp_path)
    assert mask is not None
    # A broker-labelled bar up to three hours past the UTC stamp may be EARLIER in real time.
    assert list(mask) == [False, False, True, True]
    assert F.MAX_BROKER_OFFSET_H == 3
    # A cell asking for less lag than the broker offset is held back by the offset anyway.
    tight = F.state_mask("oi_T", "iv_pct_1y", "ge", 0.8, idx, lag_hours=0, root=tmp_path)
    assert list(tight) == list(mask)


def test_family_signals_do_not_change_when_the_future_series_changes(tmp_path) -> None:
    bars = _bars(tmp_path / "u", "XAUUSD", days=200)
    avail = [t.isoformat() for t in pd.date_range(end="2026-10-03 04:00", periods=200,
                                                  freq="D", tz="UTC")]
    rng = np.random.default_rng(9)
    vals = list(rng.uniform(0, 1, 200))
    _write_series(tmp_path / "a", "oi_X", avail, vals)
    dirty = vals[:150] + [1.0 - v for v in vals[150:]]
    _write_series(tmp_path / "b", "oi_X", avail, dirty)
    kw = {"source": "oi_X", "feature": "iv_pct_1y", "op": "ge", "threshold": 0.8}
    a = F.family_implied_vol_state(bars, **kw, series_root=tmp_path / "a")
    b = F.family_implied_vol_state(bars, **kw, series_root=tmp_path / "b")
    assert a, "the fixture must fire or the test is vacuous"
    cut = pd.Timestamp(avail[150])
    early_a = [(s.time, s.side) for s in a if s.time < cut]
    early_b = [(s.time, s.side) for s in b if s.time < cut]
    assert early_a and early_a == early_b
    # One signal per EPISODE: no two consecutive bars both open a trade.
    times = pd.DatetimeIndex([s.time for s in a])
    assert (times[1:] - times[:-1] > pd.Timedelta(hours=1)).all()


def test_the_families_refuse_rather_than_fall_back_to_price(tmp_path) -> None:
    bars = _bars(tmp_path / "u", "XAUUSD", days=100)
    avail = [t.isoformat() for t in pd.date_range(end="2026-10-03", periods=90, freq="D",
                                                  tz="UTC")]
    _write_series(tmp_path, "oi_X", avail, [0.9] * 90)
    base = {"source": "oi_X", "op": "ge", "threshold": 0.8, "series_root": tmp_path}
    assert F.family_implied_vol_state(bars, feature="not_a_feature", **base) == []
    assert F.family_implied_vol_state(bars, feature="iv_pct_1y", source="oi_absent",
                                      op="ge", threshold=0.8, series_root=tmp_path) == []
    assert F.family_implied_vol_state(bars, feature="iv_pct_1y", source="oi_X", op="eq",
                                      threshold=0.8, series_root=tmp_path) == []
    assert F.family_implied_vol_state(bars, feature="iv_pct_1y", source="../oi_X", op="ge",
                                      threshold=0.8, series_root=tmp_path) == []
    assert F.family_implied_vol_conditioned(bars, base_family="carry", feature="iv_pct_1y",
                                            **base) == []


def test_the_conditioned_family_keeps_only_base_signals_inside_the_state(tmp_path) -> None:
    from mt5desk.families import get_family_func

    bars = _bars(tmp_path / "u", "XAUUSD", days=300)
    avail = [t.isoformat() for t in pd.date_range(end="2026-10-03 04:00", periods=300,
                                                  freq="D", tz="UTC")]
    vals = [0.9 if (i // 20) % 2 else 0.1 for i in range(300)]
    _write_series(tmp_path, "oi_X", avail, vals)
    base = get_family_func("trend_ma_cross")(bars)
    kept = F.family_implied_vol_conditioned(bars, base_family="trend_ma_cross", source="oi_X",
                                            feature="iv_pct_1y", op="ge", threshold=0.8,
                                            series_root=tmp_path)
    assert base and kept and len(kept) < len(base)
    assert {s.time for s in kept} <= {s.time for s in base}


# ------------------------------------------------------------------ classification ----
def test_every_family_it_mints_is_registered_buildable_and_in_options_implied() -> None:
    from mt5desk.families_orthogonal import (
        FAMILY_INPUTS,
        ORTHOGONAL_FAMILIES,
        timeframe_refusal,
    )
    from research.axis_registry import FAMILY_TABLE
    from research.gauntlet_buildability import BUILDABLE, family_verdict
    from research.miner_candidate_compiler import _registered_family

    from libs.research.alpha_clusters import classify_family, classify_sleeve

    for fam in ("implied_vol_state", "implied_vol_conditioned"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS
        assert _registered_family(fam)
        assert classify_family(fam) == "options_implied"
        assert classify_sleeve(f"XAUUSD_{fam}") == "options_implied"
        assert FAMILY_TABLE[fam][0] == "gamma_hedging_state"
        assert family_verdict(fam)[0] == BUILDABLE
        assert timeframe_refusal(fam, "H1") is None and timeframe_refusal(fam, "M5")


def test_the_grid_mints_both_arms_per_symbol_and_skips_what_it_cannot_measure(tmp_path) -> None:
    from libs.research.alpha_clusters import classify_family

    days = _days(400)
    iv = dict(zip(days, _walk(400, 18.0, 4), strict=True))
    with_rv = P.build_features(iv, rv=pd.Series(_walk(400, 15.0, 5), index=days))
    no_rv = P.build_features(iv)
    cells, skipped = P.build_cells({"XAUUSD": with_rv, "EURUSD": no_rv})
    by_sym: dict[str, set[str]] = {}
    for c in cells:
        by_sym.setdefault(c["symbol"], set()).add(c["evidence"]["condition"])
        assert classify_family(c["family"]) == "options_implied"
        assert c["alpha_cluster"] == "options_implied"
        assert c["params"]["source"] == f"oi_{c['symbol']}"
        assert c["params"]["timeframe"] in ("H1", "H4")
        assert c["falsifier"] and c["mechanism"] and c["required_data"]
        assert "reference" in c["evidence"]["history"]
    assert {"vrp_rich", "vrp_cheap"} <= by_sym["XAUUSD"]
    assert not {"vrp_rich", "vrp_cheap", "term_inverted"} & by_sym["EURUSD"]
    assert any("vrp" in why for why in skipped["EURUSD"])
    per_cond = sum(len(h) * len(P.DIRECTIONS) for h in P.DIRECT_HOLDS.values()) + len(P.BASES)
    assert len([c for c in cells if c["symbol"] == "XAUUSD"]) == per_cond * len(by_sym["XAUUSD"])


# ------------------------------------------------------------------ the pass ----
def _point(monkeypatch, tmp_path: Path) -> list[tuple[str, list[dict], int]]:
    import proposer_common as PC

    monkeypatch.setattr(P, "SERIES_DIR", tmp_path / "lake" / "series")
    monkeypatch.setattr(P, "STATE_DIR", tmp_path / "lake" / "options_implied")
    monkeypatch.setattr(P, "REFERENCE_DIR", tmp_path / "lake" / "options_implied" / "reference")
    monkeypatch.setattr(P, "DONATED", tmp_path / "lake" / "options_implied" / "donated.json")
    monkeypatch.setattr(P, "FORGE_FEED", tmp_path / "lake" / "axes" / "options_implied.json")
    monkeypatch.setattr(P, "REPORT", tmp_path / "reports" / "OPTIONS_IMPLIED.json")
    sent: list[tuple[str, list[dict], int]] = []

    def fake_donate(source: str, candidates: list[dict], tests_run: int) -> Path:
        sent.append((source, list(candidates), tests_run))
        PC.LAST_DONATION.clear()
        PC.LAST_DONATION.update({"donated": len(candidates)})
        return tmp_path / "contract.json"

    monkeypatch.setattr(PC, "donate", fake_donate)
    return sent


def test_one_pass_writes_series_feeds_the_forge_and_donates_each_cell_once(
        monkeypatch, tmp_path) -> None:
    sent = _point(monkeypatch, tmp_path)
    uni = tmp_path / "universe"
    _bars(uni, "XAUUSD")
    _bars(uni, "US500", seed=6)
    doc = P.run(source=_source(), registry=REGISTRY, universe_dir=uni,
                archive=tmp_path / "no_archive.jsonl", now=NOW)
    assert doc["status"] == "RAN" and doc["promotion_authority"] is False
    assert set(doc["symbols"]) == {"XAUUSD", "US500", "EURUSD", "XTIUSD"}
    assert doc["symbols"]["XAUUSD"]["rv"] == "MEASURED"
    assert doc["symbols"]["EURUSD"]["rv"].startswith("UNMEASURED")
    assert doc["backtestable_on_desk_vintages"] is False
    for sym in REGISTRY:
        assert (tmp_path / "lake" / "series" / f"oi_{sym}.parquet").exists()
    us500 = pd.read_parquet(tmp_path / "lake" / "series" / "oi_US500.parquet")
    assert us500["slope_9d_30d"].notna().sum() > 100           # the VIX curve reached US500
    assert {c["family"] for c in sent[0][1]} == {"implied_vol_state", "implied_vol_conditioned"}
    assert sent[0][0] == "options_implied" and sent[0][2] == len(sent[0][1])
    assert doc["grid"]["by_symbol"]["US500"] > doc["grid"]["by_symbol"]["EURUSD"]
    rep = json.loads((tmp_path / "reports" / "OPTIONS_IMPLIED.json").read_text())
    assert rep["seat"] == "options_implied"
    # Terms floor 2026-10-06: the note rides on the series, the feed and the report.
    assert rep["terms_note"] == va.TERMS_NOTE and set(us500["terms_note"]) == {va.TERMS_NOTE}
    assert rep["sources"]["refused"][0]["status"] == "FAIL_CLOSED_TERMS"
    feed = json.loads((tmp_path / "lake" / "axes" / "options_implied.json").read_text())
    assert feed["terms_note"] == va.TERMS_NOTE

    again = P.run(source=_source(), registry=REGISTRY, universe_dir=uni,
                  archive=tmp_path / "no_archive.jsonl", now=NOW)
    assert again["donated"]["fresh"] == 0 and len(sent) == 1   # no identity is charged twice

    # The cell the gauntlet will rebuild reads the series this pass wrote, and fires.
    cell = next(c for c in sent[0][1] if c["family"] == "implied_vol_state"
                and c["symbol"] == "XAUUSD")
    params = {k: v for k, v in cell["params"].items() if k != "timeframe"}
    bars = pd.read_parquet(uni / "XAUUSD_H1.parquet")
    sigs = F.family_implied_vol_state(bars, **params, series_root=tmp_path / "lake" / "series")
    assert isinstance(sigs, list)


def test_the_forge_feed_is_read_by_the_world_model(monkeypatch, tmp_path) -> None:
    from research import world_model as wm

    _point(monkeypatch, tmp_path)
    uni = tmp_path / "universe"
    _bars(uni, "XAUUSD")
    P.run(source=_source(), registry={"XAUUSD": {}}, universe_dir=uni,
          archive=tmp_path / "no_archive.jsonl", now=NOW)
    feed = json.loads((tmp_path / "lake" / "axes" / "options_implied.json").read_text())
    assert {"XAUUSD.iv_level", "XAUUSD.vrp"} <= set(feed["series"])
    monkeypatch.setattr(wm, "AXES", tmp_path / "no_axes")
    monkeypatch.setattr(wm, "LAKE_AXES", tmp_path / "lake" / "axes")
    monkeypatch.setattr(wm, "FRED", tmp_path / "no_fred.json")
    monkeypatch.setattr(wm, "REPRESENTATIONS", tmp_path / "no_repr")
    monkeypatch.setattr(wm, "MOAT_SERIES", tmp_path / "no_moat.json")
    inputs = wm.load_inputs()
    ids = {s.series_id for s in inputs.series}
    assert "options_implied:XAUUSD.iv_level" in ids
    one = next(s for s in inputs.series if s.series_id == "options_implied:XAUUSD.iv_level")
    first = one.sorted().points[0]
    # The world model's own pad lands the forge on the families' instant, never earlier.
    assert pd.Timestamp(first.available_time) == pd.Timestamp(P.knowable_at(
        first.period_time)[1])


def test_with_fred_held_the_pass_is_unmeasured_and_mints_nothing(monkeypatch, tmp_path) -> None:
    sent = _point(monkeypatch, tmp_path)
    asked: list[str] = []
    uni = tmp_path / "universe"
    _bars(uni, "XAUUSD")
    doc = P.run(source=va.FredVolSource(fetch=lambda u, t: asked.append(u) or ""),
                registry=REGISTRY, universe_dir=uni, archive=tmp_path / "no_archive.jsonl",
                now=NOW)
    assert asked == [], "a held source sends no request"
    assert doc["status"] == "UNMEASURED" and doc["grid"]["total"] == 0 and sent == []
    assert {r["status"] for r in doc["symbols"].values()} == {"UNMEASURED"}
    assert {p["status"] for p in doc["reference"].values()} == {"HELD_PENDING_TERMS"}
    assert doc["sources"]["admitted"] is False


# ------------------------------------------------------------------ the wiring ----
def test_the_producer_is_a_leg_on_the_box_clock_before_the_world_model() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    call = re.search(r'oim = _costed\("options_implied", lambda: _producer\("options_implied",'
                     r'\s*"research/options_implied\.py", "--once"\)\)', src)
    assert call, "the leg must be the standard _costed/_producer spelling"
    assert call.start() < src.index('wmd = _costed("world_model"')
    assert call.start() < src.index('rfg = _costed("representation_forge"')
    assert '"options_implied": oim' in src

    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as hc
    assert hc.LEG_DEPARTMENT["options_implied"] == "data"
    assert LEG_LAYER["options_implied"] == "prediction"


def test_the_forcer_no_longer_calls_the_cluster_unreachable() -> None:
    import empty_cluster_forcer as ecf

    _donatable, registered = ecf._families_by_cluster()
    assert {"implied_vol_state", "implied_vol_conditioned"} <= set(registered["options_implied"])
    assert "options_implied" in ecf.CLUSTER_PROPOSER
    assert "UNREACHABLE BY VENUE" not in ecf.MISSING_ARTIFACT["options_implied"]


def test_the_cluster_register_reads_blocked_pending_terms_while_every_vol_source_is_held(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import empty_cluster_forcer as ecf
    from recorders import vol_archive as va

    assert not any(ev.get("permits_use") for ev in va.TERMS_EVIDENCE.values())
    hold = ecf.terms_hold("options_implied")
    assert hold and hold["reason"] == (
        "vol sources held pending a licensed source (FRED FAQ Q3, CBOE licence, "
        "Yahoo ToS 2.4(i))")
    # The register: options_implied is listed (empty or not) and reads BLOCKED_PENDING_TERMS,
    # never UNREACHABLE, PROPOSER_OWNED or FORCED, and no cell is minted for it.
    for empty in ([], ["options_implied"]):
        (tmp_path / "b.json").write_text(json.dumps({"clusters": {"empty_in_both": empty}}))
        monkeypatch.setattr(ecf, "BREADTH", tmp_path / "b.json")
        monkeypatch.setattr(ecf, "MANDATE", tmp_path / "missing.json")
        doc = ecf.plan()
        row = next(r for r in doc["clusters"] if r["cluster"] == "options_implied")
        assert row["verdict"] == row["status"] == "BLOCKED_PENDING_TERMS"
        assert row["reason"] == hold["reason"]
        assert not [c for c in doc["cells"] if c.get("alpha_cluster") == "options_implied"]


def test_the_terms_hold_lifts_only_when_the_record_admits_a_source(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import empty_cluster_forcer as ecf
    from recorders import vol_archive as va

    ev = {k: dict(v) for k, v in va.TERMS_EVIDENCE.items()}
    ev["fred"]["permits_use"] = True
    monkeypatch.setattr(va, "TERMS_EVIDENCE", ev)
    assert ecf.terms_hold("options_implied") is None
    assert ecf.terms_hold("news_reaction") is None
