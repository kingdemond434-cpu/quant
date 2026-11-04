"""Data-class gaps #4 (agri supply), #5 (nowcast vintages) and #2 (implied vol / PROXY family).

No network. Fixtures (tests/fixtures/data_class_gap) follow each publisher's documented shape:
NASS Quick Stats `api_GET` rows, FAS OpenData export-sales records per destination, the WASDE
as-reported report-data CSV columns, the Minneapolis Fed `mpd_stats.csv` columns and an ADS index
table. Values are synthetic. None of the live bodies could be read from the build sandbox (its
proxy refuses every host), so each live schema is UNMEASURED until the box fetches it; the
parsers fail by NAME (unparseable / empty), never as a zero. The xlsx files are built here with
the stdlib so the reader is tested without openpyxl, as the box may run it.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import data_class_gap as G  # noqa: E402
from research import fetch_alfred as A  # noqa: E402
from research import options_implied as O  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "data_class_gap"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    """A minimal valid .xlsx (inline strings, numbers) written with the stdlib."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        wb = ['<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
              "<sheets>"]
        rels = ['<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                'relationships">']
        for i, (name, rows) in enumerate(sheets.items(), 1):
            wb.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
            rels.append(f'<Relationship Id="rId{i}" Type="worksheet" '
                        f'Target="worksheets/sheet{i}.xml"/>')
            xml = ['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
                   'main"><sheetData>']
            for r, row in enumerate(rows, 1):
                xml.append(f'<row r="{r}">')
                for c, v in enumerate(row):
                    ref = f"{chr(65 + c)}{r}"
                    if v is None:
                        continue
                    if isinstance(v, str):
                        xml.append(f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>')
                    else:
                        xml.append(f'<c r="{ref}"><v>{v}</v></c>')
                xml.append("</row>")
            xml.append("</sheetData></worksheet>")
            zf.writestr(f"xl/worksheets/sheet{i}.xml", "".join(xml))
        wb.append("</sheets></workbook>")
        rels.append("</Relationships>")
        zf.writestr("xl/workbook.xml", "".join(wb))
        zf.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
    return buf.getvalue()


def _serial(d: date) -> int:
    return (d - date(1899, 12, 30)).days


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = tmp_path / "world_datasets"
    monkeypatch.setattr(W, "STORE", s)
    monkeypatch.setattr(W, "OBS", s / "obs")
    monkeypatch.setattr(W, "KEYS", s / "keys.json")
    monkeypatch.setattr(W, "EXPOSURE", s / "exposure.json")
    monkeypatch.setattr(W, "MIN_REQUEST_GAP_S", 0.0)
    W._universe_at.cache_clear()
    return tmp_path


# ------------------------------------------------------------------- release instants ----
def test_release_instants_follow_each_calendar_and_err_late():
    # Memorial Day 2026-05-25: crop progress moves to Tuesday 16:00 EDT (20:00 UTC)
    assert W.crop_progress_release(date(2026, 5, 24)) == "2026-05-26T20:00:00+00:00"
    assert W.crop_progress_release(date(2026, 6, 7)) == "2026-06-08T20:00:00+00:00"
    # an ordinary week: Thursday 08:30 EDT
    assert W.export_sales_release(date(2026, 10, 15)) == "2026-10-22T12:30:00+00:00"
    # Thanksgiving Thursday, and a Monday holiday earlier in the release week: Friday
    assert W.export_sales_release(date(2026, 11, 19)) == "2026-11-27T13:30:00+00:00"
    assert W.export_sales_release(date(2026, 5, 21)) == "2026-05-29T12:30:00+00:00"
    # WASDE noon Eastern, across the DST change
    assert W.wasde_release(date(2026, 7, 10)) == "2026-07-10T16:00:00+00:00"
    assert W.wasde_release(date(2026, 12, 10)) == "2026-12-10T17:00:00+00:00"
    assert date(2026, 11, 26) in W.us_federal_holidays(2026)       # Thanksgiving
    assert date(2026, 7, 3) in W.us_federal_holidays(2026)         # July 4 is a Saturday


def test_without_a_tz_database_eastern_falls_back_late(monkeypatch):
    import zoneinfo

    def boom(*_a, **_k):
        raise zoneinfo.ZoneInfoNotFoundError("no tzdata")
    monkeypatch.setattr(zoneinfo, "ZoneInfo", boom)
    # EST (UTC-5) all year: a summer 16:00 EDT release is stamped an hour LATE, never early
    assert W._et_utc(date(2026, 6, 8), 16, 0) == "2026-06-08T21:00:00+00:00"


# ---------------------------------------------------------------------------- parsers ----
def test_nass_condition_national_only_with_good_excellent_and_release_stamp():
    df = W._nass_frame(_fx("nass_corn_condition.json"), "corn")
    codes = set(df["series_code"])
    assert "corn_condition_good_excellent" in codes
    ge = df[df["series_code"] == "corn_condition_good_excellent"].sort_values("period")
    assert ge["value"].tolist() == [68.0, 70.0, 66.0]
    # the period is the Monday starting the week ending Sunday 2026-06-07; released Mon 16:00 ET
    row = ge[ge["period"] == "2026-06-01"].iloc[0]
    assert row["release_utc"] == "2026-06-08T20:00:00+00:00"
    assert not any("poor" in c for c in codes)                     # (D) is absent, not zero
    assert 77.0 not in set(df["value"])                            # the IOWA state row is not read


def test_nass_error_document_is_a_named_failure():
    with pytest.raises(W.FetchError) as e:
        W._nass_frame(json.dumps({"error": ["bad request - invalid query"]}).encode(), "corn")
    assert e.value.reason == "api_error"


def test_esr_sums_destinations_and_stamps_the_thursday_after():
    df = W._fas_esr_frame(_fx("fas_esr_401.json"), "corn", 2026)
    ns = df[df["series_code"] == "corn_net_sales"].sort_values("period")
    assert ns["value"].tolist() == [1_000_000.0, 800_000.0]
    first = ns.iloc[0]
    assert first["period"] == "2026-10-09"                         # Fri starting the week to 10-15
    assert first["release_utc"] == "2026-10-22T12:30:00+00:00"


def test_wasde_current_projection_stocks_to_use_per_commodity_stem():
    df = W._wasde_frame(_fx("wasde_report_data.csv"))
    stu = dict(zip(df["series_code"], df["value"], strict=False))
    assert stu["wasde_us_corn_stocks_to_use"] == pytest.approx(2100 / 15000)
    assert stu["wasde_world_soybeans_stocks_to_use"] == pytest.approx(125 / 500)
    assert stu["wasde_us_corn_ending_stocks"] == 2100.0            # the projection, not 2025/26
    assert not any("brazil" in c for c in df["series_code"])
    stems = dict(zip(df["series_code"], df["stem"], strict=False))
    assert stems["wasde_us_corn_stocks_to_use"] == "CORN"
    assert stems["wasde_us_rice_ending_stocks"] == ""              # unmapped, recorded as such
    assert set(df["release_utc"]) == {"2026-10-09T16:00:00+00:00"}
    series = W.series_from_long(df, freq="monthly", hint="WASDE corn soybeans wheat")
    corn = next(s for s in series if s["code"] == "wasde_us_corn_stocks_to_use")
    assert corn["stems"] == ["CORN"] and "release_utc" not in corn["dims"]


def test_wasde_zip_and_html_are_handled_by_name():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("oce-wasde-report-data-2015-12.csv", _fx("wasde_report_data.csv"))
    assert len(W._wasde_frame(buf.getvalue())) > 0
    with pytest.raises(W.FetchError) as e:
        W._wasde_frame(b"<!doctype html><html>not found</html>")
    assert e.value.reason == "served_html"


def test_xlsx_reader_and_nowcast_vintages_long_and_wide():
    d0 = date(2026, 7, 31)
    long = _xlsx({"TrackingArchives": [
        ["Forecast Date", "Quarter being forecasted", "GDP Nowcast"],
        [_serial(d0), "2026Q3", 2.1],
        [_serial(d0 + timedelta(days=7)), "2026Q3", 2.6],
        [_serial(d0 + timedelta(days=7)), "2026Q2", 1.9],
    ]})
    v = W.nowcast_vintages(long)
    assert (d0, (2026, 3), 2.1) in v and (d0 + timedelta(days=7), (2026, 3), 2.6) in v
    df = W._nowcast_frame(long, "gdpnow")
    q0 = df[df["series_code"] == "gdpnow_q0"]["value"].tolist()
    assert q0 == [2.1, 2.6]
    rev = df[df["series_code"] == "gdpnow_q0_rev"]["value"].tolist()
    assert rev == [pytest.approx(0.5)]                             # the news the vintage carried
    assert df[df["series_code"] == "gdpnow_qm1"]["value"].tolist() == [1.9]
    assert set(df["release_utc"]) >= {"2026-07-31T22:00:00+00:00"}  # 18:00 EDT
    wide = _xlsx({"Download": [["Timestamp", "2026:Q3", "2026:Q4"],
                               ["2026-10-02", 2.0, None], ["2026-10-09", 2.2, 1.7]]})
    dfw = W._nowcast_frame(wide, "nyfed")
    assert dfw[dfw["series_code"] == "nyfed_q0"]["value"].tolist() == [1.7]   # Q4 is q0 in Oct
    assert dfw[dfw["series_code"] == "nyfed_qm1"]["value"].tolist() == [2.0, 2.2]


def test_every_vintage_is_kept_and_a_revision_is_a_new_row(store):
    def frame(v: float) -> pd.DataFrame:
        return pd.DataFrame({"series_code": ["x"], "period": ["2026-10-02"], "value": [v],
                             "release_utc": ["2026-10-02T22:00:00+00:00"]})
    s1 = W.series_from_long(frame(2.0), freq="daily")
    f1, n1 = W.merge_observations(None, s1, now=NOW)
    assert n1 == 1 and str(f1["available_time"].iloc[0]) == "2026-10-02 22:00:00+00:00"
    f2, n2 = W.merge_observations(f1, W.series_from_long(frame(2.4), freq="daily"),
                                  now=NOW + timedelta(days=1))
    assert n2 == 1 and len(f2) == 2 and sorted(f2["vintage"].tolist()) == [1, 2]
    # the research door serves the FIRST vintage it saw
    assert W.pit_series(f2, "x").iloc[0] == 2.0


def test_ads_parser_reads_colon_dates():
    df = W._ads_frame(_fx("ads_index.csv"))
    assert df["period"].tolist() == ["2026-10-20", "2026-10-21", "2026-10-22"]
    assert df["value"].tolist() == [-0.12, -0.10, -0.15]


# --------------------------------------------------------------- doors, keys and terms ----
def test_doors_stand_on_quoted_rows_and_no_ideas_only_source_is_a_door():
    doors = W.agri_nowcast_doors(NOW)
    want = {"USDA_NASS": "usda_nass_quickstats", "USDA_FAS": "usda_fas_esr",
            "USDA_WASDE": "usda_wasde", "NYFED": "nyfed_web"}
    for d in doors:
        for part in d.get("urls") or [{"url": d["url"]}]:
            url = part["url"].replace("{api_key}", "x")
            assert tf.source_of_url(url) == want[d["provider"]], url
            assert tf.input_source(url) is None                       # live input permitted
        assert tf.terms_state(want[d["provider"]]) == "READ"
    every = " ".join(json.dumps(d) for d in W.direct_sources(NOW))
    for host in ("atlantafed.org", "philadelphiafed.org", "minneapolisfed.org", "conab",
                 "eurex.com"):
        assert host not in every                                     # no live door to them
    for key in ("atlanta_fed", "philly_fed", "minneapolis_fed_mpd", "conab_brazil",
                "eurex_web"):
        assert tf.live_input_status(key) == tf.IDEAS_ONLY
        assert tf.terms_state(key) == "READ"
        assert tf.platform_of_url(f"https://{next(iter(tf.SOURCE_POLICY[key]['hosts']))}/") \
            is None                                                  # ideas still mined
    assert tf.input_source("https://www.atlantafed.org/-/media/x/gdpnow/a.xlsx") == "atlanta_fed"
    lines = W.ideas_only_lines()
    assert {ln["policy_row"] for ln in lines} == {"atlanta_fed", "philly_fed", "conab_brazil"}
    assert all(ln["delta_elogw"] == "UNMEASURED" and ln["status"] == tf.IDEAS_ONLY
               for ln in lines)


def _fetcher(seen: list[str]):
    def fetch(url: str, timeout: float) -> bytes:
        seen.append(url)
        if "quickstats.nass.usda.gov" in url:
            return _fx("nass_corn_condition.json")
        if "esr/exports" in url:
            if url.endswith("/2027"):
                raise W.FetchError("not_found_404", "no such market year yet")
            return _fx("fas_esr_401.json")
        if "oce-wasde-report-data" in url:
            return _fx("wasde_report_data.csv")
        raise W.FetchError("not_found_404", "x")
    return fetch


def test_nass_needs_its_key_by_name_and_never_writes_it(store, monkeypatch):
    monkeypatch.setattr(W, "direct_sources", lambda now=None: W.agri_nowcast_doors(NOW))
    monkeypatch.delenv("NASS_API_KEY", raising=False)
    seen: list[str] = []
    cat = W._blank_catalog()
    stats: Counter[str] = Counter()
    W.fetch_direct(W.Client(_fetcher(seen), 1e18), cat, now=NOW, until=1e18, stats=stats,
                   qstats=Counter(), by_provider={p: Counter() for p in
                                                  ("USDA_NASS", "USDA_FAS", "USDA_WASDE",
                                                   "NYFED")})
    nass = {k: v for k, v in cat["datasets"].items() if k.startswith("USDA_NASS/")}
    assert nass and all(v["fail_reason"] == "needs_key" for v in nass.values())
    assert not any("quickstats" in u for u in seen)
    # the other doors landed; a market year the API does not hold yet is a counted miss
    esr = cat["datasets"]["USDA_FAS/ESR_401"]
    assert esr["lifecycle"] in ("INGESTED", "QUALITY-PASSED")
    assert esr["partial_misses"] == {"not_found_404": 1}
    assert cat["datasets"]["USDA_WASDE/wasde_balance"]["rows"] > 0
    assert cat["datasets"]["NYFED/staff_nowcast"]["fail_reason"] == "not_found_404"
    # first fetch of an empty dataset adds the backfill files; the next pass does not
    assert sum("oce-wasde-report-data-2010-04-to-2015-12.zip" in u for u in seen) == 1

    secret = "NASSkey0123456789abcdef"  # noqa: S105 -- a fixture value, asserted never written
    monkeypatch.setenv("NASS_API_KEY", secret)
    cat2 = W._blank_catalog()
    W.fetch_direct(W.Client(_fetcher(seen), 1e18), cat2, now=NOW, until=1e18, stats=stats,
                   qstats=Counter(), by_provider={p: Counter() for p in
                                                  ("USDA_NASS", "USDA_FAS", "USDA_WASDE",
                                                   "NYFED")})
    assert cat2["datasets"]["USDA_NASS/CORN_CONDITION"]["rows"] > 0
    blob = json.dumps(cat2) + "".join(p.read_text("utf-8")
                                      for p in (store / "world_datasets").rglob("*.json"))
    assert secret not in blob
    frame = pd.read_parquet(W.dataset_path("USDA_NASS", "CORN_CONDITION"))
    ge = frame[frame["series_code"] == "corn_condition_good_excellent"]
    assert str(ge["available_time"].min()) == "2026-06-01 20:00:00+00:00"   # Mon 16:00 EDT
    meta = json.loads(W.meta_path("USDA_WASDE", "wasde_balance").read_text("utf-8"))
    corn = meta["series"]["wasde_us_corn_stocks_to_use"]
    assert corn["stems"] == ["CORN"]                             # never every softs symbol


def test_agri_mapping_records_what_reaches_no_symbol():
    uni = (("CORN", "Soft Commodity", "USD"), ("SUGARRAW", "Soft Commodity", "USD"),
           ("EURUSD", "Forex", "USD"))
    m = W.agri_mapping(uni)
    assert m["mapped"] == {"corn": ["CORN"], "sugar": ["SUGARRAW"]}
    assert "coffee" in m["unmapped"] and "rice" in m["unmapped"]
    assert "matches no hypothesis-lane symbol" in m["unmapped"]["wheat"]


# --------------------------------------------------------------- implied vol and PROXY ----
def test_mpd_parser_reads_markets_and_measures():
    df = O.mpd_frame(_fx("mpd_stats.csv"))
    assert {"gold_sd", "gold_skew", "euro_princ"} <= set(df["series_code"])
    assert df[df["series_code"] == "gold_skew"]["value"].tolist() == [-0.31, -0.35]


def test_no_implied_source_is_live_and_each_carries_a_missed_growth_line():
    rows = O.implied_sources()
    assert rows and all(r["live_input"] != "PERMITTED" for r in rows)
    for r in rows:
        assert r["missed_growth"]["delta_elogw"] == "UNMEASURED"


def _bars(days: int = 160, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=days * 24, freq="h", tz="UTC")
    r = rng.normal(0, 0.001, len(idx))
    close = 1.1 * np.exp(np.cumsum(r))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)


def test_proxy_features_are_causal_and_sane():
    b = _bars()
    f = O.proxy_features(b)
    assert {"rv_5d", "rv_63d", "rv_term_5_63", "rskew_63d", "downside_share_21d"} <= set(f)
    last = f.dropna().iloc[-1]
    assert 0.0 < last["rv_21d"] < 1.0 and 0.0 <= last["downside_share_21d"] <= 1.0
    # appending the future never changes a past day's value
    more = pd.concat([b, _bars(200, seed=9).iloc[160 * 24:]])
    g = O.proxy_features(more)
    common = f.dropna().index
    pd.testing.assert_frame_equal(f.loc[common], g.loc[common])
    assert O.proxy_features(_bars(40)).empty                       # too short says so


def test_proxy_lands_labelled_and_mapped_to_its_own_symbol(store, tmp_path):
    bars_dir = tmp_path / "bars"
    bars_dir.mkdir()
    _bars().to_parquet(bars_dir / "EURUSD_H1.parquet")
    rep = O.run(now=NOW, bars=bars_dir, symbols=["EURUSD", "GBPUSD"])
    assert rep["proxy"]["symbols_computed"] == 1 and rep["proxy"]["no_h1_bars"] == 1
    assert rep["label"].startswith("PROXY")
    meta = json.loads(W.meta_path("MT5_PROXY", "RVOL_EURUSD").read_text("utf-8"))
    for code, s in meta["series"].items():
        assert s["name"].startswith("PROXY realized"), code
        assert s["stems"] == ["EURUSD"] and s["currencies"] == []
    frame = pd.read_parquet(W.dataset_path("MT5_PROXY", "RVOL_EURUSD"))
    assert (frame["available_time"] - frame["period_end"]).min() == pd.Timedelta(days=1)
    again = O.run(now=NOW + timedelta(hours=1), bars=bars_dir, symbols=["EURUSD"])
    assert again["proxy"]["fresh_skipped"] == 1                    # once a day, not every hour


# ------------------------------------------------------------------------------ ALFRED ----
def test_alfred_once_without_key_reports_needs_key_and_exits_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "api_key", lambda: None)
    monkeypatch.setattr(A, "REPORTS", tmp_path)
    assert A.main(["--once"]) == 0
    rep = json.loads((tmp_path / "alfred_vintages.json").read_text("utf-8"))
    assert rep["status"] == "NEEDS_KEY" and rep["written"] == 0


def test_alfred_once_renews_the_stalest_few(tmp_path):
    import os
    for i, sid in enumerate(("GDPC1", "PAYEMS", "UNRATE")):
        p = tmp_path / f"{sid}.parquet"
        p.write_bytes(b"x")
        t = NOW.timestamp() - (10 + 30 * i) * 3600
        os.utime(p, (t, t))
    due = A.stale_series({"GDPC1", "PAYEMS", "UNRATE", "CPIAUCSL"}, NOW, limit=2,
                         out_dir=tmp_path)
    assert due == ["CPIAUCSL", "UNRATE"]                           # absent first, then oldest
    assert all(not re.search(r"[a-z]", s) for s in A.SERIES)       # government ids only


# ------------------------------------------------------------------- gap module + wiring ----
def test_both_legs_are_wired_and_the_gap_module_names_them():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    from libs.research.layers import LEG_LAYER
    from research import hourly_cycle as H
    for leg, mod, var in (("options_implied", "research/options_implied.py", "opi"),
                          ("fetch_alfred", "research/fetch_alfred.py", "alf")):
        assert re.search(rf'_costed\("{leg}", lambda: _producer\(\s*"{leg}",\s*"{mod}"', src)
        assert re.search(rf'"{leg}": {var}\b', src)
        assert leg in H.LEG_DEPARTMENT and leg in H.LEG_BUDGET_SEC and leg in LEG_LAYER
    spec = {c["id"]: c for c in G.CLASSES}
    assert "research/world_dataset_hunter.py" in spec["agri_supply"]["producers"]
    assert "research/options_implied.py" in spec["options_implied_vol"]["producers"]
    idx = G.code_hosts(ROOT, ("desks/mt5/research",))
    for cid in ("usda_nass_quickstats", "usda_fas_esr", "usda_wasde"):
        url = next(c["url"] for c in spec["agri_supply"]["candidates"] if c["id"] == cid)
        exact, _ = G.url_files(url, idx)
        assert "desks/mt5/research/world_dataset_hunter.py" in exact, cid


def test_a_proxy_only_class_never_reads_as_covered():
    spec = next(c for c in G.CLASSES if c["id"] == "options_implied_vol")
    assert spec["coverage_cap"][0] == "PRODUCER"
    row = G.measure_class(spec, idx={}, legs={"research/options_implied.py": "options_implied"},
                          clocks={}, runtime={"leg:options_implied": {
                              "artifact": "desks/mt5/reports/OPTIONS_IMPLIED.json"}},
                          catalogues={}, now=NOW, tracked=None)
    assert row["coverage"] == "PRODUCER" and row["coverage_capped"]["to"] == "PRODUCER"
    assert row["gap_score"] > 0
