"""Rows 112/113: the HIBOR-SOFR carry state (USDHKD), the S$NEER band state (USDSGD) and the MAS
statement calendar. Offline: every network read is a fixture behind a fake door."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries import asia_rv_states as A  # noqa: E402
from research.countries.hk import carry_state as HK  # noqa: E402
from research.countries.sg import band_state as SG  # noqa: E402
from research.countries.sg import pack as SGP  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "asia_rv"
NOW = datetime(2026, 11, 18, 6, 0, tzinfo=UTC)


class Door:
    """A fake network: fixtures by host/path, and a log of every URL asked for."""

    def __init__(self, robots: str = "robots_allow.txt", status: int | None = None) -> None:
        self.asked: list[str] = []
        self.robots = (FIX / robots).read_text("utf-8")
        self.status = status

    def __call__(self, url: str) -> str:
        self.asked.append(url)
        if url.endswith("/robots.txt"):
            return self.robots
        if self.status is not None:
            raise A.HardStop(self.status, url)
        if "api.hkma.gov.hk" in url:
            return (FIX / "hkma_interbank_liquidity.json").read_text("utf-8")
        if "markets.newyorkfed.org" in url:
            return (FIX / "nyfed_sofr.json").read_text("utf-8")
        raise AssertionError(f"unexpected fetch {url}")


def _bars(start: str, end: str, close: float) -> pd.DataFrame:
    idx = pd.date_range(start, end, freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    return pd.DataFrame({"close": np.full(len(idx), close)}, index=idx)


def _basket(start: str = "2020-01-02", end: str = "2022-06-30", **override: float):
    px = {"USDSGD": 1.35, "USDCNH": 6.9, "EURSGD": 1.5, "SGDJPY": 80.0, "AUDSGD": 0.95,
          "GBPSGD": 1.75, **override}
    frames = {s: _bars(start, end, v) for s, v in px.items()}
    return lambda sym: frames.get(sym)


def _run(tmp_path: Path, door: Door, **kw):
    return A.run(now=NOW, fetch=door, store_dir=tmp_path / "store",
                 series_dir=tmp_path / "series", bars=_basket(),
                 calendar_path=tmp_path / "mas_mps.json", **kw)


# ------------------------------------------------------------------------------ the registry

def test_every_source_carries_its_terms_and_only_open_rows_are_fetchable() -> None:
    rows = A.registry()
    ids = {r["id"] for r in rows}
    assert {"hkma_interbank_liquidity", "nyfed_sofr", "mas_website", "hkex_securities_prices",
            "hk_adr_h_basis", "fred_sofr"} <= ids
    for r in rows:
        assert r["terms"] in ("OPEN", "TERMS_BLOCKED", "BLOCKED_INPUT", "REFUSED"), r["id"]
        assert r["terms_clause"] and r["terms_read"], r["id"]
        assert A.fetchable(r) == (r["terms"] == "OPEN" and r["adapter"] in ("hkma_api",
                                                                            "nyfed_sofr"))
    by = {r["id"]: r for r in rows}
    assert by["mas_website"]["terms"] == "TERMS_BLOCKED"
    assert by["hkex_securities_prices"]["terms"] == "TERMS_BLOCKED"
    assert by["hk_adr_h_basis"]["terms"] == "BLOCKED_INPUT"
    assert not any("fred" in str(r.get("url")) for r in rows if A.fetchable(r))


def test_a_blocked_source_is_reported_and_never_fetched(tmp_path: Path) -> None:
    door = Door()
    doc = _run(tmp_path, door)
    assert not any(h in u for u in door.asked
                   for h in ("hkex.com.hk", "mas.gov.sg", "fred.stlouisfed.org"))
    st = {s["id"]: s for s in doc["sources"]}
    assert st["hkex_securities_prices"]["status"] == "TERMS_BLOCKED"
    assert st["mas_website"]["status"] == "TERMS_BLOCKED"
    assert doc["series"]["hk_adr_h_basis"]["status"] == "BLOCKED_INPUT"


# ------------------------------------------------------------------------------ fetch manners

def test_robots_is_read_before_any_data_and_a_disallow_fetches_nothing(tmp_path: Path) -> None:
    door = Door(robots="robots_deny.txt")
    doc = _run(tmp_path, door)
    assert all(u.endswith("/robots.txt") for u in door.asked)
    assert {s["status"] for s in doc["sources"] if s["id"] in
            ("hkma_interbank_liquidity", "nyfed_sofr")} == {"UNMEASURED"}
    assert doc["series"][HK.SERIES_ID]["status"].startswith("UNMEASURED")


def test_a_refusal_is_a_hard_stop_held_in_state(tmp_path: Path) -> None:
    _run(tmp_path, Door(status=403))
    state = json.loads((tmp_path / "store" / "state.json").read_text("utf-8"))
    assert set(state["hard_stops"]) == {"hkma_interbank_liquidity", "nyfed_sofr"}
    again = Door()
    doc = _run(tmp_path, again)
    assert again.asked == []
    assert {s["status"] for s in doc["sources"] if s["id"] == "nyfed_sofr"} == {"HARD_STOP"}


def test_a_source_read_today_is_not_read_again_within_the_hour(tmp_path: Path) -> None:
    _run(tmp_path, Door())
    second = Door()
    _run(tmp_path, second)
    assert second.asked == []


# ------------------------------------------------------------------------------ HK carry

def test_the_carry_series_is_hibor_minus_sofr_on_matched_dates(tmp_path: Path) -> None:
    doc = _run(tmp_path, Door())
    info = doc["series"][HK.SERIES_ID]
    assert info["status"] == "BUILT" and info["targets"] == ["USDHKD"]
    df = pd.read_parquet(tmp_path / "series" / f"{HK.SERIES_ID}.parquet")
    hk = json.loads((FIX / "hkma_interbank_liquidity.json").read_text())["result"]["records"]
    sofr = {r["effectiveDate"]: r["percentRate"]
            for r in json.loads((FIX / "nyfed_sofr.json").read_text())["refRates"]}
    row = next(r for r in hk if r["end_of_date"] == "2026-06-01")
    got = df[df["event_time"] == pd.Timestamp("2026-06-01", tz="UTC")].iloc[0]
    assert got["hibor_on_sofr"] == pytest.approx(row["hibor_overnight"] - sofr["2026-06-01"])
    assert got["hibor_1m_sofr"] == pytest.approx(row["hibor_fixing_1m"] - sofr["2026-06-01"])
    # 2026-07-03 has no SOFR print (a federal holiday): no carry row, never a filled one
    assert not (df["event_time"] == pd.Timestamp("2026-07-03", tz="UTC")).any()


def test_no_carry_row_is_available_before_both_legs_were_published(tmp_path: Path) -> None:
    _run(tmp_path, Door())
    df = pd.read_parquet(tmp_path / "series" / f"{HK.SERIES_ID}.parquet")
    for _, r in df.iterrows():
        day = pd.Timestamp(r["event_time"]).date().isoformat()
        at = pd.Timestamp(r["available_time"])
        assert at >= HK.sofr_available(day) and at >= HK.hkma_available(day)
        assert at > pd.Timestamp(r["event_time"]) + pd.Timedelta(hours=12)
    # Thursday 2026-07-02: SOFR comes out on Monday 07-06 (Friday 07-03 is the July 4th holiday)
    assert HK.sofr_available("2026-07-02") == pd.Timestamp("2026-07-06 13:00", tz="UTC")
    # HKMA's Friday figures are stamped Monday 09:00 Hong Kong time
    assert HK.hkma_available("2026-07-10") == pd.Timestamp("2026-07-13 01:00", tz="UTC")


def test_the_first_print_is_kept_and_a_revision_is_counted_not_backdated() -> None:
    store: dict = {}
    t0 = datetime(2026, 11, 17, 12, tzinfo=UTC)
    HK.merge_first(store, {"2026-11-16": {"sofr": 3.9}}, "sofr", t0)
    first_at = store["2026-11-16"]["available_time"]
    m = HK.merge_first(store, {"2026-11-16": {"sofr": 3.95}}, "sofr",
                       datetime(2026, 11, 18, 12, tzinfo=UTC))
    assert m == {"added": 0, "revised": 1}
    assert store["2026-11-16"]["v"]["sofr"] == 3.9
    assert store["2026-11-16"]["available_time"] == first_at
    # read live, before its rule: stamped at the rule, never at the read
    assert pd.Timestamp(first_at) == HK.sofr_available("2026-11-16")
    # read live, after its rule: stamped at the read
    late: dict = {}
    seen = datetime(2026, 11, 18, 20, tzinfo=UTC)
    HK.merge_first(late, {"2026-11-16": {"sofr": 3.9}}, "sofr", seen)
    assert pd.Timestamp(late["2026-11-16"]["available_time"]) == pd.Timestamp(seen)


def test_a_malformed_page_parses_to_nothing_never_to_zeros() -> None:
    assert HK.parse_hkma({"header": {"success": False}}) == ({}, None)
    assert HK.parse_hkma({"result": {"records": [{"end_of_date": "x"}]}})[0] == {}
    assert HK.parse_sofr({"refRates": [{"effectiveDate": "2026-01-02", "percentRate": None}]}) \
        == {}


# ------------------------------------------------------------------------------ SG band

def test_the_band_starts_at_the_first_recentring_and_crawls_at_the_slope() -> None:
    band, info = SG.build(_basket())
    assert info["status"] == "BUILT" and info["targets"] == ["USDSGD"]
    ev = pd.to_datetime(band["event_time"])
    assert ev.min() >= pd.Timestamp("2020-03-30")       # nothing before the anchor
    # a flat basket sits at the centre while the slope is zero (2020-03-30 .. 2021-10-14)
    flat = band[(ev > pd.Timestamp("2020-04-01")) & (ev < pd.Timestamp("2021-10-13"))]
    assert np.allclose(flat["band_pos"], 0.0)
    # then the centre crawls up at 0.5%/yr (2021-10-14) and 1.0%/yr (2022-01-25), so a flat
    # basket falls through the band: one year at 0.5%/yr is a quarter of the 2% half-width
    after = band[(ev > pd.Timestamp("2022-01-26")) & (ev < pd.Timestamp("2022-04-14"))]
    assert (after["band_pos"] < 0).all()
    assert after["band_pos"].is_monotonic_decreasing
    # 2022-04-14 re-centres to the prevailing level: back at the centre
    re = band[ev > pd.Timestamp("2022-04-14")]
    assert abs(float(re["band_pos"].iloc[0])) < 0.01


def test_a_stronger_basket_reads_higher_in_the_band() -> None:
    weak, _ = SG.build(_basket())
    # every SGD cross moved 1% stronger from 2021 on (the anchor was set flat in 2020)
    strong_from = "2021-01-04"
    base = _basket()

    def strong(sym: str):
        df = base(sym)
        if df is None:
            return None
        df = df.copy()
        k = df.index >= pd.Timestamp(strong_from, tz="UTC")
        f = 1.01 if sym == "SGDJPY" else 1 / 1.01
        df.loc[k, "close"] = df.loc[k, "close"] * f
        if sym == "USDCNH":
            df.loc[k, "close"] = df.loc[k, "close"] / f       # CNH is not an SGD pair
        return df

    hi, _ = SG.build(strong)
    w = weak.set_index("event_time")["band_pos"]
    h = hi.set_index("event_time")["band_pos"]
    j = pd.concat([w, h], axis=1, keys=["w", "h"]).dropna()
    j = j[j.index > pd.Timestamp(strong_from)]
    j = j[j.index < pd.Timestamp("2022-04-14")]
    # 1% stronger is log(1.01) / 2% = about half the half-width
    assert np.allclose(j["h"] - j["w"], np.log(1.01) / SG.HALF_WIDTH, atol=1e-9)


def test_no_band_row_uses_a_later_bar_or_a_later_statement() -> None:
    base = _basket()
    band, _ = SG.build(base)

    def shocked(sym: str):
        df = base(sym)
        if df is None:
            return None
        df = df.copy()
        df.loc[df.index >= pd.Timestamp("2021-06-01", tz="UTC"), "close"] *= 1.2
        return df

    alt, _ = SG.build(shocked)
    a = band.set_index("event_time")["band_pos"]
    b = alt.set_index("event_time")["band_pos"]
    early = a.index < pd.Timestamp("2021-05-31")
    assert np.allclose(a[early], b[early])
    # each row is available only after its own broker day closed (true UTC)
    from libs.regime.session_clock import server_to_utc
    day_end = server_to_utc(pd.DatetimeIndex(band["event_time"]) + pd.Timedelta(hours=23))
    assert (pd.DatetimeIndex(pd.to_datetime(band["available_time"], utc=True)) >= day_end).all()


def test_a_missing_leg_is_unmeasured_not_a_smaller_basket() -> None:
    base = _basket()
    band, info = SG.build(lambda s: None if s == "USDCNH" else base(s))
    assert band.empty and info["status"].startswith("UNMEASURED")


def test_the_weights_sum_to_one_and_the_record_agrees_with_the_pack() -> None:
    assert sum(SG.WEIGHTS.values()) == pytest.approx(1.0)
    rec = {d: (s, r, o) for d, s, r, o in SG.MPS_RECORD}
    for row in SGP.BAND_STATE:
        assert row["date"] in rec, row["date"]
        assert ("re-cent" in row["centre"]) == rec[row["date"]][1], row["date"]
        assert ("OFF-CYCLE" in row["action"]) == rec[row["date"]][2], row["date"]
    for days in SGP.CENTRAL_BANK["dates"].values():
        for d in days:
            assert d in rec and not rec[d][2], d


# ------------------------------------------------------------------------------ the calendar

def test_the_calendar_is_the_scheduled_record_and_the_clock_reads_it() -> None:
    held = json.loads(SG.CALENDAR_PATH.read_text("utf-8"))
    assert held == SG.calendar_doc(), "regenerate with band_state.write_calendar()"
    assert held["tz"] == "Asia/Singapore"
    for off in ("2020-03-30", "2022-01-25", "2022-07-14"):
        assert off not in held["dates"]
    assert held["dates"]["2026-10-14"] == "08:00"
    from mt5desk import local_clock as LC
    cal = LC.calendar("mas_mps")
    assert cal is not None and cal[0] == "Asia/Singapore"


def test_the_mps_cell_fires_only_in_the_statement_hour() -> None:
    from mt5desk import local_clock as LC
    # broker stamps (New York + 7h) for 2026-10-13..15; 08:00 SGT = 00:00 UTC = 03:00 broker
    idx = pd.date_range("2026-10-13", "2026-10-15 23:00", freq="h", tz="UTC")
    mask = LC.calendar_mask(idx, "mas_mps", "contains")
    assert mask is not None
    hit = idx[mask]
    assert len(hit) == 1 and str(hit[0]) == "2026-10-14 03:00:00+00:00"


def test_the_recipes_read_what_this_organ_writes(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    from research import culture_gap_cells as G
    recs = {r["id"]: r for r in G.recipes()}
    assert recs["hk_hibor_sofr_carry_state"]["pack"] == HK.SERIES_ID
    assert recs["hk_hibor_sofr_carry_state"]["symbols"] == ["USDHKD"]
    assert recs["sg_neer_band_state"]["pack"] == SG.SERIES_ID
    assert recs["sg_neer_band_state"]["symbols"] == ["USDSGD"]
    assert recs["sg_mas_mps_hour"]["calendar"] == "mas_mps"
    _run(tmp_path, Door())
    monkeypatch.setattr(G, "SERIES_DIR", tmp_path / "series")
    assert G.pack_signals(HK.SERIES_ID)[0] == ["hibor_on_sofr", "hibor_1m_sofr"]
    assert G.pack_signals(SG.SERIES_ID)[0] == ["band_pos"]
    from mt5desk import family_exogenous_conditioner as X
    s = X.conditioner(HK.SERIES_ID, "hibor_on_sofr", "level_z", root=tmp_path / "series")
    assert s is not None and len(s) > 0
