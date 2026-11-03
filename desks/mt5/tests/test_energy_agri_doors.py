"""Natgas storage surprise, CPC population-weighted degree days and the agri doors' liveness.

The doors extend research/world_dataset_hunter.py (the gap-agri-nowcast data line): EIA's
weekly storage stamped at the WNGSR release instant with the five-year-average surprise, NOAA
CPC daily degree days (daily, storage-week and five-year departures), NASS cotton progress and
sugarbeets, an ENERGY_AGRI liveness watch, and an access label per door. Fixtures are written
from each publisher's documented public format: this sandbox's proxy refuses every host.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402
from research import data_class_gap as G  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
NGS = "NG.NW2_EPG0_SWO_R48_BCF.W"


# ------------------------------------------------------------------------------ fixtures ----
def _storage_level(d: date) -> float:
    return round(2500 + 1000 * math.sin(d.timetuple().tm_yday / 365 * 2 * math.pi)
                 + (d.year - 2016) * 10 + (d.toordinal() % 5), 0)


def eia_ngs_payload(start: date = date(2016, 1, 1), end: date = date(2026, 10, 30),
                    skip: frozenset[date] = frozenset()) -> bytes:
    """EIA API v2 `/v2/seriesid/` response shape: response.data[] rows, newest first, values as
    strings (the documented v2 format)."""
    rows = []
    d = start
    while d <= end:
        if d not in skip:
            rows.append({"period": d.isoformat(), "series-description": "Weekly Lower 48 States "
                         "Natural Gas Working Underground Storage (Billion Cubic Feet)",
                         "value": f"{_storage_level(d):.0f}", "units": "BCF"})
        d += timedelta(days=7)
    return json.dumps({"response": {"total": len(rows), "frequency": "weekly",
                                    "data": rows[::-1]},
                       "apiVersion": "2.1.8"}).encode()


def _dd(d: date, kind: str) -> int:
    x = 15 * math.cos(d.timetuple().tm_yday / 365 * 2 * math.pi) + (d.toordinal() % 3)
    return max(0, round(x if kind == "Heating" else -x + 2))


def cpc_year_file(year: int, kind: str, end: date = date(2026, 10, 31),
                  weights: str = "Population", missing: frozenset[date] = frozenset()) -> bytes:
    """CPC `daily_data/<year>/Population.<Kind>.txt`: the header block, then the pipe table
    `Region|YYYYMMDD|...` with census divisions 1-9 and the CONUS row (documented format,
    read 2026-11-03)."""
    days = []
    d = date(year, 1, 1)
    while d <= min(date(year, 12, 31), end):
        days.append(d)
        d += timedelta(days=1)
    head = (f"---\nProduct: Daily {kind} Degree Days\nRegions: CPC::Regions::CensusDivisions\n"
            f"Weights: {weights}\n")
    lines = ["Region|" + "|".join(x.strftime("%Y%m%d") for x in days)]
    for r in range(1, 10):
        lines.append(f"{r}|" + "|".join(str(_dd(x, kind) + r) for x in days))
    lines.append("CONUS|" + "|".join("-9999" if x in missing else str(_dd(x, kind))
                                     for x in days))
    return (head + "\n".join(lines) + "\n").encode()


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = tmp_path / "world_datasets"
    monkeypatch.setattr(W, "STORE", s)
    monkeypatch.setattr(W, "OBS", s / "obs")
    monkeypatch.setattr(W, "KEYS", s / "keys.json")
    monkeypatch.setattr(W, "EXPOSURE", s / "exposure.json")
    monkeypatch.setattr(W, "CATALOG", s / "catalog.json")
    monkeypatch.setattr(W, "MIN_REQUEST_GAP_S", 0.0)
    W._universe_at.cache_clear()
    W._exposure_at.cache_clear()
    return tmp_path


def _fetcher(seen: list[str], *, cpc_fail: bool = False):
    def fetch(url: str, timeout: float) -> bytes:
        seen.append(url)
        if "api.eia.gov" in url and NGS in url:
            return eia_ngs_payload()
        if "degree_days/weighted/daily_data" in url:
            if cpc_fail:
                raise W.FetchError("not_found_404", "x")
            y = int(url.rsplit("/", 2)[-2])
            return cpc_year_file(y, "Heating" if "Heating" in url else "Cooling")
        raise W.FetchError("not_found_404", "x")
    return fetch


_DIRECT_SOURCES = W.direct_sources


def _energy_doors() -> list[dict[str, Any]]:
    return [d for d in _DIRECT_SOURCES(NOW) if d.get("liveness") == W.ENERGY_AGRI
            and d["provider"] in ("EIA", "NOAA_CPC")]


def _run(cat: dict[str, Any], seen: list[str], **kw: Any) -> None:
    W.fetch_direct(W.Client(_fetcher(seen, **kw), 1e18), cat, now=NOW, until=1e18,
                   stats=Counter(), qstats=Counter(),
                   by_provider={p: Counter() for p in ("EIA", "NOAA_CPC")})


# ---------------------------------------------------------------------- release instants ----
def test_storage_release_follows_eias_schedule_and_its_alternates():
    # standard: Thursday 10:30 ET (EST after 1 November -> 15:30 UTC; EDT -> 14:30 UTC)
    assert W.ngs_release(date(2026, 10, 30)) == "2026-11-05T15:30:00+00:00"
    assert W.ngs_release(date(2026, 10, 16)) == "2026-10-22T14:30:00+00:00"
    # the schedule's alternates, verbatim: Veterans Day Fri 10:30, Thanksgiving Wed 12:00,
    # Christmas 2025 Monday 29 December 12:00, New Year 2026 Wednesday 31 December 12:00
    assert W.ngs_release(date(2026, 11, 6)) == "2026-11-13T15:30:00+00:00"
    assert W.ngs_release(date(2026, 11, 20)) == "2026-11-25T17:00:00+00:00"
    assert W.ngs_release(date(2025, 12, 19)) == "2025-12-29T17:00:00+00:00"
    assert W.ngs_release(date(2025, 12, 26)) == "2025-12-31T17:00:00+00:00"
    assert W.ngs_release(date(2025, 1, 3)) == "2025-01-08T17:00:00+00:00"


def test_an_unscheduled_holiday_week_errs_late():
    # 2024 Thanksgiving: EIA released Wednesday 27 Nov 12:00 ET; the rule must never be earlier
    assert W.ngs_release(date(2024, 11, 22)) >= "2024-11-27T17:00:00+00:00"
    # Christmas 2024 (a Wednesday) -> Friday noon, never the Thursday
    assert W.ngs_release(date(2024, 12, 20)) == "2024-12-27T17:00:00+00:00"
    # an ordinary 2024 week is the plain Thursday
    assert W.ngs_release(date(2024, 10, 4)) == "2024-10-10T14:30:00+00:00"


def test_degree_day_release_is_two_days_later_at_14_utc():
    assert W.cpc_dd_release(date(2026, 10, 31)) == "2026-11-02T14:00:00+00:00"


# ---------------------------------------------------------------------- storage surprise ----
def test_storage_surprise_is_change_minus_the_five_year_same_week_change():
    df = W._eia_ngs_frame(eia_ngs_payload(), "ng")
    got = {(r.series_code, r.period): r.value for r in df.itertuples()}
    wk = date(2026, 10, 30)
    chg = _storage_level(wk) - _storage_level(wk - timedelta(days=7))
    assert got[("ng_change", wk.isoformat())] == chg
    lvl = {d: _storage_level(d) for d in
           (date(2016, 1, 1) + timedelta(days=7 * i) for i in range(600))}
    prior = []
    for k in range(1, 6):
        anchor = wk.replace(year=wk.year - k)
        hit = next(d for off in range(4) for d in (anchor - timedelta(days=off),
                                                   anchor + timedelta(days=off)) if d in lvl)
        prior.append(lvl[hit] - lvl[hit - timedelta(days=7)])
    avg = sum(prior) / 5
    assert got[("ng_change_5y_avg", wk.isoformat())] == pytest.approx(avg)
    assert got[("ng_surprise", wk.isoformat())] == pytest.approx(chg - avg)
    # every derived row of a week carries that week's release instant, never a period date
    assert set(df[df["period"] == wk.isoformat()]["release_utc"]) == {W.ngs_release(wk)}


def test_no_five_year_value_without_five_prior_years_or_across_a_gap():
    df = W._eia_ngs_frame(eia_ngs_payload(skip=frozenset({date(2026, 10, 23)})), "ng")
    codes = set(df[df["period"] == "2026-10-30"]["series_code"])
    assert "ng_change" not in codes and "ng_surprise" not in codes   # 14 days apart: no change
    assert "ng" in codes
    assert set(df[df["period"] == "2016-01-29"]["series_code"]) == {"ng", "ng_change"}


def test_eia_error_document_is_a_named_failure():
    with pytest.raises(W.FetchError) as e:
        W._eia_ngs_frame(b'{"error": "invalid api_key"}', "ng")
    assert e.value.reason == "unparseable"


# -------------------------------------------------------------------------- degree days ----
def test_cpc_reads_conus_only_with_kind_from_the_file_and_missing_absent():
    miss = date(2026, 3, 3)
    df = W._cpc_degree_day_frame(cpc_year_file(2026, "Heating", missing=frozenset({miss})))
    assert set(df["series_code"]) == {"hdd_us_pop"}
    assert miss.isoformat() not in set(df["period"])
    row = df[df["period"] == "2026-01-02"].iloc[0]
    assert row["value"] == _dd(date(2026, 1, 2), "Heating")             # CONUS, not division 1
    assert row["release_utc"] == "2026-01-04T14:00:00+00:00"
    cool = W._cpc_degree_day_frame(cpc_year_file(2026, "Cooling"))
    assert set(cool["series_code"]) == {"cdd_us_pop"}
    for bad in (cpc_year_file(2026, "Heating", weights="Area"), b"<!doctype html><p>x"):
        with pytest.raises(W.FetchError):
            W._cpc_degree_day_frame(bad)


def test_weekly_degree_days_sum_the_storage_week_and_carry_five_year_departures():
    df = pd.concat([W._cpc_degree_day_frame(cpc_year_file(y, k)) for y in range(2019, 2027)
                    for k in ("Heating", "Cooling")], ignore_index=True)
    out = W._degree_day_features(df)
    got = {(r.series_code, r.period): r for r in out.itertuples()}
    fri = date(2026, 10, 30)
    days = [fri - timedelta(days=i) for i in range(7)]
    hdd = sum(_dd(d, "Heating") for d in days)
    cdd = sum(_dd(d, "Cooling") for d in days)
    sat = (fri - timedelta(days=6)).isoformat()
    assert got[("hdd_us_pop_wk", sat)].value == hdd
    assert got[("tdd_us_pop_wk", sat)].value == hdd + cdd
    assert got[("hdd_us_pop_wk", sat)].release_utc == W.cpc_dd_release(fri)
    assert got[("hdd_us_pop_wk", sat)].freq == "weekly"
    assert ("hdd_us_pop_wk_vs_5y", sat) in got
    # the week holding 31 October (ends Friday 6 November) is incomplete: absent, never partial
    assert ("hdd_us_pop_wk", "2026-10-31") not in got
    d = date(2026, 2, 10)
    want = _dd(d, "Heating") - sum(_dd(d.replace(year=d.year - k), "Heating")
                                   for k in range(1, 6)) / 5
    assert got[("hdd_us_pop_vs_5y", d.isoformat())].value == pytest.approx(want)
    assert ("hdd_us_pop_vs_5y", "2023-02-10") not in got                 # only 4 prior years


# -------------------------------------------------- the door path: PIT, key, cell path ----
def test_doors_land_stamped_never_write_the_key_and_reach_xngusd(store, monkeypatch):
    monkeypatch.setattr(W, "direct_sources", lambda now=None: _energy_doors())
    secret = "EIAkey0123456789abcdef"  # noqa: S105 -- a fixture value, asserted never written
    monkeypatch.setenv("EIA_API_KEY", secret)
    cat = W._blank_catalog()
    _run(cat, [])
    ngs = cat["datasets"][f"EIA/{NGS}"]
    dd = cat["datasets"]["NOAA_CPC/DEGREE_DAYS_POP"]
    assert ngs["rows"] > 0 and dd["rows"] > 0
    assert ngs["pack_state"] == dd["pack_state"] == "FETCHED" and dd["empty_streak"] == 0
    blob = json.dumps(cat) + "".join(p.read_text("utf-8")
                                     for p in (store / "world_datasets").rglob("*.json"))
    assert secret not in blob
    frame = pd.read_parquet(W.dataset_path("EIA", NGS))
    s = frame[(frame["series_code"] == "natgas_storage_l48_surprise")
              & (frame["period"] == "2026-10-30")]
    assert str(s["available_time"].iloc[0]) == "2026-11-05 15:30:00+00:00"   # Thu 10:30 EST
    dframe = pd.read_parquet(W.dataset_path("NOAA_CPC", "DEGREE_DAYS_POP"))
    w = dframe[(dframe["series_code"] == "tdd_us_pop_wk") & (dframe["period"] == "2026-10-24")]
    assert str(w["available_time"].iloc[0]) == "2026-11-01 14:00:00+00:00"
    assert (dframe["available_time"] > dframe["period_end"]).all()       # never the period date
    # the cell path: exposure maps the features to XNGUSD, which world_macro_proposer reads
    W.build_exposure(NOW)
    W._exposure_at.cache_clear()
    meta = json.loads(W.meta_path("EIA", NGS).read_text("utf-8"))
    row = meta["series"]["natgas_storage_l48_surprise"]
    assert row["quality"] == "PASS" and row["instruments"] == ["XNGUSD"]
    dmeta = json.loads(W.meta_path("NOAA_CPC", "DEGREE_DAYS_POP").read_text("utf-8"))
    passed = {c for c, v in dmeta["series"].items() if v["quality"] == "PASS"}
    assert {"hdd_us_pop", "tdd_us_pop_wk", "hdd_us_pop_wk_vs_5y"} <= passed
    doc = W._exposure_doc()
    assert row["key"] in doc["symbols"]["XNGUSD"]
    assert W.exposed_keys("XNGUSD", now=NOW)
    assert all(row["key"] not in ks for sym, ks in doc["symbols"].items() if sym != "XNGUSD")


def test_the_proposer_tests_the_storage_features_as_world_macro_state_cells(store,
                                                                            monkeypatch):
    from research import proposer_common as pc
    from research import world_macro_proposer as P
    monkeypatch.setattr(W, "direct_sources", lambda now=None: _energy_doors())
    monkeypatch.setenv("EIA_API_KEY", "k")
    _run(W._blank_catalog(), [])
    W.build_exposure(NOW)
    W._exposure_at.cache_clear()
    W._keys_at.cache_clear()
    W._frame_at.cache_clear()
    idx = pd.date_range(end="2026-10-31 23:00", periods=30000, freq="h", tz="UTC")
    rng = np.random.default_rng(3)
    close = 3.0 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    bars = pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": 100}, index=idx)
    monkeypatch.setattr(P, "REPORT", store / "WORLD_MACRO_PROPOSER.json")
    monkeypatch.setattr(pc, "bars", lambda sym: bars)
    monkeypatch.setattr(pc, "cost_frac", lambda sym, meta, close: 0.0)
    monkeypatch.setattr(pc, "artifact_hours", lambda d: {})
    rep = P.run(budget_s=300, now=NOW, donate=False)
    assert rep["status"] == "OK" and rep["tests_run"] > 0
    assert "XNGUSD" not in rep["skipped"]


# --------------------------------------------------------------------------- liveness ----
def _due_now(cat: dict[str, Any]) -> None:
    for r in cat["datasets"].values():
        r["next_due"] = None


def test_a_door_empty_more_than_two_runs_is_red_and_reaches_the_organ_status(store,
                                                                             monkeypatch):
    monkeypatch.setattr(W, "direct_sources", lambda now=None: _energy_doors())
    monkeypatch.setenv("EIA_API_KEY", "k")
    cat = W._blank_catalog()
    states = []
    for _ in range(3):
        _due_now(cat)
        _run(cat, [], cpc_fail=True)
        rep = W.energy_agri_report(cat, NOW)
        states.append(next(d["state"] for d in rep["doors"]
                           if d["door"] == "NOAA_CPC/DEGREE_DAYS_POP"))
    assert states == ["AMBER", "AMBER", "RED"]
    assert rep["red_doors"] == ["NOAA_CPC/DEGREE_DAYS_POP"]
    assert rep["status"].startswith("RED: energy/agri doors empty > 2 runs")
    red = next(d for d in rep["doors"] if d["state"] == "RED")
    assert red["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert next(d for d in rep["doors"] if d["door"] == f"EIA/{NGS}")["state"] == "GREEN"
    _due_now(cat)
    _run(cat, [])                                                      # one landing resets it
    assert W.energy_agri_report(cat, NOW)["status"] == "OK"
    assert cat["datasets"]["NOAA_CPC/DEGREE_DAYS_POP"]["empty_streak"] == 0


def test_a_missing_key_is_needs_key_never_red(store, monkeypatch):
    monkeypatch.setattr(W, "direct_sources", lambda now=None: _energy_doors())
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    cat = W._blank_catalog()
    seen: list[str] = []
    for _ in range(4):
        _due_now(cat)
        _run(cat, seen)
    assert not any("api.eia.gov" in u for u in seen)
    eia = next(d for d in W.energy_agri_report(cat, NOW)["doors"] if d["door"] == f"EIA/{NGS}")
    assert eia["state"] == "NEEDS_KEY" and eia["key"] == "NEEDS_KEY:EIA_API_KEY"


def test_the_watch_covers_energy_and_agri_and_the_organ_report_lifts_it():
    rep = W.energy_agri_report(W._blank_catalog(), NOW)
    doors = {d["door"] for d in rep["doors"]}
    assert {f"EIA/{NGS}", "NOAA_CPC/DEGREE_DAYS_POP", "USDA_WASDE/wasde_balance",
            "USDA_NASS/COTTON_PROGRESS", "USDA_NASS/SUGARBEETS_PROGRESS"} <= doors
    assert all(d["state"] in ("UNMEASURED", "NEEDS_KEY") for d in rep["doors"])
    src = (DESK / "research" / "world_dataset_hunter.py").read_text("utf-8")
    assert '"energy_agri": energy_agri,' in src and "energy_agri_report(cat, now)" in src


# ---------------------------------------------------------------- access and terms ----
def test_access_labels_follow_the_robots_reading_and_redistribution_fails_closed(monkeypatch):
    nass = W.door_access("https://quickstats.nass.usda.gov/api/api_GET/?key={api_key}")
    assert nass["access_label"] == "PUBLIC_WITH_TERMS"
    assert "Disallow" in nass["terms_note"] and nass["redistribute_allowed"] is False
    eia = W.door_access(f"https://api.eia.gov/v2/seriesid/{NGS}?api_key={{api_key}}")
    assert eia["access_label"] == "ACCESS_UNCLEAR" and eia["redistribute_allowed"] is False
    assert "unreadable" in eia["terms_note"]
    cpc = W.door_access(W.CPC_DD_DAILY + "2026/Population.Heating.txt")
    assert cpc["access_label"] == "ACCESS_UNCLEAR" and cpc["policy_row"] == "noaa_cpc"
    wasde = W.door_access("https://www.usda.gov/sites/default/files/documents/"
                          "oce-wasde-report-data-2026-10.csv")
    assert wasde["access_label"] == "OPEN_DATA" and wasde["redistribute_allowed"] is True
    broken = {k: {kk: vv for kk, vv in v.items() if kk != "allowed_uses"}
              for k, v in ac.ROUTING.items()}
    monkeypatch.setattr(ac, "ROUTING", broken)
    assert W.door_access("https://www.usda.gov/sites/default/files/documents/x.csv")[
        "redistribute_allowed"] is False                               # unreadable -> closed


def test_every_door_stands_on_a_read_terms_row_and_is_live_input():
    want = {"EIA": "eia_api", "NOAA_CPC": "noaa_cpc"}
    for d in _energy_doors():
        for part in d.get("urls") or [{"url": d["url"]}]:
            url = part["url"].replace("{api_key}", "x")
            assert tf.source_of_url(url) == want[d["provider"]], url
            assert tf.input_source(url) is None
        assert tf.terms_state(want[d["provider"]]) == "READ"
    rep = W.energy_agri_report(W._blank_catalog(), NOW)
    assert all(d["live_sizing"].startswith("PERMITTED") for d in rep["doors"])
    blob = json.dumps(W.direct_sources(NOW)).lower()
    for host in ("binance", "bybit", "okx", "hyperliquid", "coinbase"):
        assert host not in blob


def test_softs_doors_cover_cotton_and_sugar_and_map_to_tradable_symbols():
    nass = {d["dataset"]: d for d in W.agri_nowcast_doors(NOW)
            if d["provider"] == "USDA_NASS"}
    assert nass["COTTON_PROGRESS"]["stems"] == ["COTTON"]
    assert nass["SUGARBEETS_PROGRESS"]["stems"] == ["SUGAR"]
    assert all(d["liveness"] == W.ENERGY_AGRI for d in nass.values())
    for stem, sym in (("SUGAR", "SUGAR"), ("COTTON", "COTTON"), ("XNG", "XNGUSD")):
        assert sym in W.instruments_for([], [stem])


def test_the_gap_census_credits_the_degree_day_door():
    spec = {c["id"]: c for c in G.CLASSES}
    url = next(c["url"] for c in spec["weather_climate"]["candidates"]
               if c["id"] == "noaa_cpc_degree_days")
    exact, _ = G.url_files(url, G.code_hosts(ROOT, ("desks/mt5/research",)))
    assert "desks/mt5/research/world_dataset_hunter.py" in exact
