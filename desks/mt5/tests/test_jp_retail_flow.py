"""Japan retail and investor-type flow doors (TFX Click 365, JPX investor type, FFAJ OTC FX).

No network: every request goes through an injected transport. Fixtures
(desks/mt5/tests/fixtures/jp_retail_flow/, built from each publisher's documented layout because the
cloud proxy refuses tfx.co.jp, jpx.co.jp and ffaj.or.jp to curl; live shape UNMEASURED from here):
  tfx_weekly_sellbuy.xls     為替売買動向: pairs down, four Tuesdays x (売建玉, 買建玉) across;
                             values SYNTHETIC (one ラージ row that must not be summed)
  stock_1_w_20261019_20261023.xlsx  JPX's published TSE Prime figures for 2026-10-19..23 (read
                             from the PDF 2026-11-03): 株数 group then 金額 group; a SYNTHETIC
                             Standard-market block below it that must not be picked
  stock_val_1_261003.xls     the archive's value-only layout, period in a title cell; SYNTHETIC,
                             with one non-conserving row that must be dropped
  ffaj_trading_vol_and_position.xls  months down, 売建玉 / 買建玉 in 億円; 2026-09 is the
                             published figure (43,358 / 73,799), the rest SYNTHETIC
  *.html                     index / archive / fx_flash pages with the published href shapes
"""
from __future__ import annotations

import json
import sys
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
from research import jp_retail_flow as J  # noqa: E402
from research import universe_policy as up  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "jp_retail_flow"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
UNIVERSE_ROWS = {s: {"asset_class": "Forex", "currency_profit": "JPY"}
                 for s in ("USDJPY", "AUDJPY", "EURJPY", "ZARJPY")}
UNIVERSE_ROWS["JPN225"] = {"asset_class": "Indices", "currency_profit": "JPY"}
ALLOW = b"User-agent: *\nAllow: /\n"


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


ROUTES: dict[str, object] = {
    "weekly_sellbuy.xls": _fx("tfx_weekly_sellbuy.xls"),
    "investor-type/index.html": _fx("jpx_index.html"),
    "00-00-archives-00.html": _fx("jpx_archive.html"),
    "00-00-archives-01.html": b"<html></html>",
    "stock_1_w_20261019_20261023.xlsx": _fx("stock_1_w_20261019_20261023.xlsx"),
    "stock_val_1_261003.xls": _fx("stock_val_1_261003.xls"),
    "performance/fx_flash": _fx("ffaj_fx_flash.html"),
    "trading_vol_and_position.xls": _fx("ffaj_trading_vol_and_position.xls"),
}


def _transport(routes: dict[str, object] | None = None, robots: object = ALLOW):
    """First route whose key is in the URL wins; a value that is an exception is raised.
    robots.txt answers `robots`. Every URL asked is recorded."""
    table = dict(ROUTES if routes is None else routes)
    calls: list[str] = []

    def t(url: str, timeout: float) -> bytes:
        calls.append(url)
        hit = robots if url.endswith("/robots.txt") else next(
            (v for k, v in table.items() if k in url), J.Missing(url))
        if isinstance(hit, Exception):
            raise hit
        assert isinstance(hit, bytes)
        return hit

    t.calls = calls  # type: ignore[attr-defined]
    return t


@pytest.fixture()
def box(tmp_path, monkeypatch):
    store = tmp_path / "world_datasets"
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(UNIVERSE_ROWS), "utf-8")
    reg = tmp_path / "data_registry.json"
    reg.write_text(json.dumps({"schema_version": 1, "datasets": {}}), "utf-8")
    for name, val in (("STORE", store), ("OBS", store / "obs"),
                      ("CATALOG", store / "catalog.json"), ("EXPOSURE", store / "exposure.json"),
                      ("KEYS", store / "keys.json"), ("HISTORY", store / "hunt_history.jsonl"),
                      ("REGISTRY", reg), ("UNIVERSE", uni), ("PACK_LIVENESS", tmp_path / "pl.json"),
                      ("REPORT", tmp_path / "DATASET_HUNT.json"), ("DESK", tmp_path),
                      ("MIN_REQUEST_GAP_S", 0.0)):
        monkeypatch.setattr(W, name, val)
    monkeypatch.setattr(up, "UNIVERSE", uni)
    monkeypatch.setattr(W, "_free_disk_ok", lambda: (True, {"free_gb": 99.0}))
    monkeypatch.setattr(W, "direct_sources", lambda now=None: [])
    monkeypatch.setattr(W, "LEGACY_PROBES", {})
    monkeypatch.setattr(W, "COUNTRY_PACKS", {})
    monkeypatch.setattr(W, "fetch_country_packs", lambda *a, **k: None)
    monkeypatch.setattr(W, "fetch_dbnomics", lambda *a, **k: None)
    monkeypatch.setattr(W, "discover", lambda *a, **k: None)
    monkeypatch.setattr(W, "country_packs_eu_report", lambda cat, now: {})
    up._registry.cache_clear()
    for fn in (W._universe_at, W._exposure_at, W._keys_at, W._frame_at):
        fn.cache_clear()
    yield tmp_path
    up._registry.cache_clear()
    W._universe_at.cache_clear()


def _offline(*a, **k):
    raise W.FetchError("blocked_proxy", "no network in tests")


def _run(transport, now=NOW):
    return W.run(budget_s=120, fetch=_offline, labelled_fetch=transport, now=now)


def _door(rep: dict, name: str) -> dict:
    pk = rep["country_packs"]["packs"][J.PACK]
    return next(d for d in pk["doors"] if d["dataset"] == name)


# --------------------------------------------------------------------------------- parsers ----
def test_tfx_parser_reads_pairs_and_sides_by_label_and_never_sums_the_large_contract():
    recs = {(r["date"], r["symbol"]): r for r in J.parse_tfx_sellbuy(_fx("tfx_weekly_sellbuy.xls"))}
    assert {s for _, s in recs} == {"USDJPY", "AUDJPY", "EURJPY", "ZARJPY"}
    assert len(recs) == 16                                   # 4 pairs x 4 Tuesdays
    u = recs[(date(2026, 10, 27), "USDJPY")]
    assert (u["short"], u["long"]) == (131000, 390000)       # 売建玉 short, 買建玉 long; no ラージ
    a = recs[(date(2026, 10, 6), "AUDJPY")]
    assert (a["short"], a["long"]) == (30000, 260000)


def test_tfx_parser_also_reads_dates_down_the_rows():
    rows = [["日付", "米ドル/円", None, "豪ドル/円", None],
            [None, "買建玉", "売建玉", "買建玉", "売建玉"],
            ["2026/10/20", 400000, 125000, 262000, 31000],
            ["2026/10/27", 390000, 131000, 255000, 33000]]
    out: dict = {}
    J._tfx_sheet(rows, out)
    assert out[(date(2026, 10, 27), "USDJPY")] == {"long": 390000, "short": 131000}
    assert out[(date(2026, 10, 20), "AUDJPY")] == {"long": 262000, "short": 31000}


def test_jpx_parser_reads_the_value_group_of_tse_prime_and_every_row_conserves():
    got = J.parse_jpx_investor_type(_fx("stock_1_w_20261019_20261023.xlsx"),
                                    "stock_1_w_20261019_20261023.xlsx")
    assert got is not None and got["market"] == "prime"
    assert (got["week_start"], got["week_end"]) == (date(2026, 10, 19), date(2026, 10, 23))
    rows = got["rows"]
    assert set(rows) == set(J.JPX_INVESTORS.values())          # all fifteen investor types
    assert rows["foreigners"]["net"] == pytest.approx(30.398335)   # 金額 千円 -> bn JPY, not 株数
    assert rows["individuals"]["net"] == pytest.approx(-67.762676)
    assert rows["trust_banks"]["net"] == pytest.approx(-222.790281)
    assert rows["total"]["total"] == pytest.approx(82275.855774)
    for v in rows.values():
        assert v["buy"] - v["sell"] == pytest.approx(v["net"], abs=1e-6)


def test_jpx_archive_value_file_reads_its_period_and_drops_a_row_that_does_not_conserve():
    got = J.parse_jpx_investor_type(_fx("stock_val_1_261003.xls"), "stock_val_1_261003.xls")
    assert got is not None
    assert (got["week_start"], got["week_end"]) == (date(2026, 10, 13), date(2026, 10, 16))
    assert got["rows"]["foreigners"]["net"] == pytest.approx(500.0)       # 千円 -> bn JPY
    assert "investment_trusts" not in got["rows"]                 # net 999 != buy - sell


def test_jpx_links_find_value_files_and_archive_pages_never_share_counts():
    files, pages = J.jpx_links(_fx("jpx_archive.html").decode(), J.JPX_ARCHIVE)
    assert list(files) == ["stock_val_1_261003.xls"]               # stock_vol_* skipped
    assert pages == ["https://www.jpx.co.jp/markets/statistics-equities/investor-type/"
                     "00-00-archives-01.html"]


def test_ffaj_parser_and_page_reader():
    recs = J.parse_ffaj_positions(_fx("ffaj_trading_vol_and_position.xls"))
    assert len(recs) == 40
    sep = next(r for r in recs if (r["year"], r["month"]) == (2026, 9))
    assert (sep["short"], sep["long"]) == (43358, 73799)           # the published figure
    url, upd = J.ffaj_links(_fx("ffaj_fx_flash.html").decode(), J.FFAJ_PAGE)
    assert url and url.endswith("/2026/10/trading_vol_and_position.xls")
    assert upd == date(2026, 10, 15)
    assert J._month_of("令和8年9月") == (2026, 9) and J._month_of("2026/09") == (2026, 9)


# ------------------------------------------------------------------- point-in-time stamps ----
def test_publication_stamps_are_the_release_instant_never_the_period():
    # JPX: 4th Tokyo business day of the following week, 15:30 JST
    assert J.jpx_publication(date(2026, 10, 23)) == datetime(2026, 10, 29, 6, 30, tzinfo=UTC)
    # Labour Thanksgiving (Mon 2026-11-23) pushes it to Friday
    assert J.jpx_publication(date(2026, 11, 20)) == datetime(2026, 11, 27, 6, 30, tzinfo=UTC)
    # Golden Week: 4, 5, 6 May are holidays -> 7, 8, 11, 12
    assert J.jpx_publication(date(2026, 5, 1)) == datetime(2026, 5, 12, 6, 30, tzinfo=UTC)
    # TFX: the Tuesday close, the next day
    assert J.tfx_publication(date(2026, 10, 27)) == datetime(2026, 10, 28, 9, tzinfo=UTC)
    # FFAJ: the 20th of the next month, or the page's later 更新日
    assert J.ffaj_publication(2026, 9, date(2026, 10, 15)) == datetime(2026, 10, 20, 15,
                                                                        tzinfo=UTC)
    assert J.ffaj_publication(2026, 9, date(2026, 10, 22)) == datetime(2026, 10, 22, 15,
                                                                        tzinfo=UTC)
    assert J.ffaj_publication(2026, 12) == datetime(2027, 1, 20, 15, tzinfo=UTC)


def test_stored_rows_carry_the_publication_stamp(box):
    _run(_transport())
    tfx = pd.read_parquet(W.dataset_path(J.PROVIDER, J.tfx_dataset("USDJPY")))
    r = tfx[(tfx["series_code"] == "long") & (tfx["period"] == "2026-10-21")]
    assert r["period_end"].iloc[0] == pd.Timestamp("2026-10-27", tz="UTC")
    assert r["available_time"].iloc[0] == pd.Timestamp("2026-10-28 09:00", tz="UTC")
    jpx = pd.read_parquet(W.dataset_path(J.PROVIDER, J.JPX_DATASET))
    r = jpx[(jpx["series_code"] == "foreigners_net_bn") & (jpx["period"] == "2026-10-19")]
    assert r["available_time"].iloc[0] == pd.Timestamp("2026-10-29 06:30", tz="UTC")
    ff = pd.read_parquet(W.dataset_path(J.PROVIDER, J.FFAJ_DATASET))
    r = ff[(ff["series_code"] == "short") & (ff["period"] == "2026-09")]
    assert r["value"].iloc[0] == 43358
    assert r["available_time"].iloc[0] == pd.Timestamp("2026-10-20 15:00", tz="UTC")
    # a feature is stamped with its period's raw publication, never earlier
    f = ff[ff["series_code"] == "net_ratio"].set_index("period")["available_time"]
    raw = ff[ff["series_code"] == "long"].set_index("period")["available_time"]
    assert (f == raw.reindex(f.index)).all()


# ---------------------------------------------------------------------------- access labels --
def test_robots_is_a_label_and_never_stops_the_fetch():
    t = _transport()
    lab = J.access_label(J.TFX_FILE, t, J.TFX_POLICY)
    assert lab["access_label"] == "PUBLIC_WITH_TERMS"             # terms present, robots allows
    assert lab["redistribute_allowed"] is False
    dis = _transport(robots=b"User-agent: *\nDisallow: /\n")
    lab = J.access_label(J.TFX_FILE, dis, J.TFX_POLICY)
    assert lab["access_label"] == "PUBLIC_WITH_TERMS" and "Disallow" in lab["terms_note"]
    unread = _transport(robots=J.Transient("timeout"))
    lab = J.access_label(J.JPX_INDEX, unread, J.JPX_POLICY)
    assert lab["access_label"] == "ACCESS_UNCLEAR" and lab["redistribute_allowed"] is False
    absent = _transport(robots=J.Missing("robots"))
    assert J.access_label(J.FFAJ_PAGE, absent, J.FFAJ_POLICY)["access_label"] == \
        "PUBLIC_WITH_TERMS"
    with pytest.raises(J.HardStop):
        J.access_label(J.TFX_FILE, _transport(robots=J.HardStop(403, "r")), J.TFX_POLICY)
    assert J.redistribute_allowed("OPEN_DATA") is True
    assert J.redistribute_allowed("NOT_A_LABEL") is False           # fails closed


def test_a_disallowed_or_unreadable_robots_still_lands_the_data(box):
    t = _transport(robots=b"User-agent: *\nDisallow: /\n")
    rep = _run(t)
    assert any("weekly_sellbuy.xls" in u for u in t.calls)
    d = _door(rep, "TFX_CLICK365")
    assert d["state"] == "GREEN" and d["access"]["access_label"] == "PUBLIC_WITH_TERMS"
    meta = json.loads(W.meta_path(J.PROVIDER, J.tfx_dataset("USDJPY")).read_text("utf-8"))
    assert meta["access"]["access_label"] == "PUBLIC_WITH_TERMS"
    assert meta["access"]["redistribute_allowed"] is False
    assert meta["access"]["live_sizing_allowed"] is False           # research-only
    rep2 = W.run(budget_s=120, fetch=_offline, now=NOW + timedelta(days=1),
                 labelled_fetch=_transport(robots=J.Transient("dns")))
    assert _door(rep2, "FFAJ_OTC_FX")["access"]["access_label"] == "ACCESS_UNCLEAR"
    assert _door(rep2, "FFAJ_OTC_FX")["state"] == "GREEN"


def test_register_rows_quote_their_terms_and_hold_live_sizing_closed():
    for key, url in ((J.TFX_POLICY, J.TFX_FILE), (J.JPX_POLICY, J.JPX_INDEX),
                     (J.FFAJ_POLICY, "https://www.ffaj.or.jp/wp-content/uploads/2026/10/"
                                     "trading_vol_and_position.xls")):
        row = tf.SOURCE_POLICY[key]
        assert row["status"] == tf.IDEAS_ONLY and row["terms"]["checked_at"] == "2026-11-03"
        assert row["terms"]["clauses"] and tf.terms_state(key) == "READ"
        assert tf.input_source(url) == key                         # refused as LIVE input
        assert tf.platform_of_url(url) is None                     # never held: still mined
        assert J.live_sizing_allowed(key) is False
    assert "二次利用" in tf.SOURCE_POLICY[J.JPX_POLICY]["terms"]["clauses"]["secondary_use"]
    assert "著作権法を遵守" in tf.SOURCE_POLICY[J.FFAJ_POLICY]["terms"]["clauses"]["comply"]
    # route-level rows: the rest of tfx.co.jp keeps its own row (asia_collector's swap points)
    assert tf.input_source("https://www.tfx.co.jp/en/historical/fx/") is None


# ------------------------------------------------------------------------------- liveness ----
def test_a_door_that_lands_nothing_three_runs_running_turns_red_and_names_itself(box):
    routes = dict(ROUTES)
    routes["weekly_sellbuy.xls"] = b"not a workbook"
    states = []
    for k in range(3):
        rep = _run(_transport(routes), now=NOW + timedelta(hours=7 * k))
        states.append(_door(rep, "TFX_CLICK365")["state"])
    assert states == ["AMBER", "AMBER", "RED"]                    # > PACK_EMPTY_RED_RUNS
    assert rep["status"].startswith("RED") and "japan_retail_flow/TFX_CLICK365" in rep["status"]
    assert _door(rep, "JPX_INVESTOR_TYPE")["state"] == "GREEN"
    rep = _run(_transport(), now=NOW + timedelta(days=2))
    assert _door(rep, "TFX_CLICK365")["state"] == "GREEN" and rep["status"] == "OK"


@pytest.mark.parametrize("stop", [403, 429, "WAF"])
def test_an_access_control_is_a_hard_stop_held_for_a_person_and_never_retried(box, stop):
    routes = dict(ROUTES)
    routes["performance/fx_flash"] = J.HardStop(stop, J.FFAJ_PAGE, "refused")
    rep = _run(_transport(routes))
    d = _door(rep, "FFAJ_OTC_FX")
    assert d["state"] == "HARD_STOP" and d["hard_stop"]["waits_for"] == "a person"
    assert "FFAJ_OTC_FX" in rep["status"]
    again = _transport()
    rep = _run(again, now=NOW + timedelta(days=3))
    assert not any("ffaj.or.jp" in u for u in again.calls)        # no clock releases it
    assert _door(rep, "FFAJ_OTC_FX")["state"] == "HARD_STOP"


def test_hunter_transport_maps_refusals_to_hard_stops():
    def fetch(url, timeout):
        raise W.FetchError("blocked_403", url)
    with pytest.raises(J.HardStop):
        J.hunter_transport(fetch)("https://x.example/a", 5)


def test_an_injected_hunter_fetch_never_reaches_these_doors(box):
    asked: list[str] = []

    def fetch(url, timeout, **kw):
        asked.append(url)
        raise W.FetchError("blocked_proxy", url)
    rep = W.run(budget_s=60, fetch=fetch, now=NOW)
    assert not any(h in u for u in asked for h in ("click365", "jpx.co.jp", "ffaj"))
    assert _door(rep, "TFX_CLICK365")["state"] == "UNMEASURED"


# ------------------------------------------------------------------------------- features ----
def test_book_features_are_contrarian_and_point_in_time():
    idx = [f"2026-{m:02d}" for m in range(1, 13)] + [f"2027-{m:02d}" for m in range(1, 13)]
    rng = np.random.default_rng(7)
    long = pd.Series(70000 + rng.normal(0, 3000, 24), index=idx)
    short = pd.Series(40000 + rng.normal(0, 3000, 24), index=idx)
    short.iloc[-1] = 80000                                          # retail suddenly short
    wide = pd.DataFrame({"long": long, "short": short})
    f = J.ffaj_features(wide)
    assert f["net_ratio"].iloc[0] == pytest.approx((long.iloc[0] - short.iloc[0])
                                                   / (long.iloc[0] + short.iloc[0]))
    assert f["contrarian_z"].iloc[-1] > 2 and f["crowding"].iloc[-1] > 2
    assert f["contrarian_z"].iloc[:J.Z_MIN - 1].isna().all()        # no z on too little history
    head = J.ffaj_features(wide.iloc[:15])                          # the future never leaks back
    pd.testing.assert_frame_equal(head, f.iloc[:15])


def test_jpx_features_and_their_point_in_time_shape():
    idx = [(date(2025, 1, 6) + timedelta(weeks=k)).isoformat() for k in range(30)]
    rng = np.random.default_rng(3)
    wide = pd.DataFrame({"foreigners_net_bn": rng.normal(0, 200, 30),
                         "individuals_net_bn": rng.normal(0, 150, 30),
                         "trust_banks_net_bn": rng.normal(0, 50, 30),
                         "total_turnover_bn": np.full(30, 80000.0)}, index=idx)
    f = J.jpx_features(wide)
    for c in ("foreign_net_z", "individual_net_z", "foreign_minus_individual_bn",
              "foreign_net_4w_bn", "trust_bank_net_z", "foreign_net_share"):
        assert c in f.columns
    assert f["foreign_minus_individual_bn"].iloc[5] == pytest.approx(
        wide["foreigners_net_bn"].iloc[5] - wide["individuals_net_bn"].iloc[5])
    assert f["foreign_net_4w_bn"].iloc[3] == pytest.approx(wide["foreigners_net_bn"].iloc[:4].sum())
    pd.testing.assert_frame_equal(J.jpx_features(wide.iloc[:12]), f.iloc[:12])


# ----------------------------------------------------- research door and the footprint matrix --
def test_end_to_end_series_reach_research_and_the_footprint_frame(box):
    rep = _run(_transport())
    for door in J.DOORS:
        assert _door(rep, door)["state"] == "GREEN", door
    meta = json.loads(W.meta_path(J.PROVIDER, J.FFAJ_DATASET).read_text("utf-8"))
    nr = meta["series"]["net_ratio"]
    assert nr["quality"] == "PASS" and nr["instruments"] == ["AUDJPY", "USDJPY"]
    exposure = json.loads(W.EXPOSURE.read_text("utf-8"))["symbols"]
    assert nr["key"] in exposure["USDJPY"]
    jmeta = json.loads(W.meta_path(J.PROVIDER, J.JPX_DATASET).read_text("utf-8"))
    assert jmeta["series"]["foreigners_net_bn"]["n"] == 2          # two weeks: ACCRUING
    assert jmeta["access"]["live_sizing_allowed"] is False
    cat = json.loads(W.CATALOG.read_text("utf-8"))["datasets"]
    assert cat["PACK_JP/JPX_INVESTOR_TYPE"]["backfill_remaining"] == 0
    # #659's matrix rows, filled: same ids, class retail, region JP
    fp = {r["id"]: r for r in rep["player_footprint"]}
    assert set(fp) == {"tfx_click365", "jpx_investor_type", "ffaj_otc_fx"}
    assert all(r["class"] == "retail" and r["region"] == "JP" for r in fp.values())
    tfx = J.footprint_frame("tfx_click365")
    assert {"usdjpy_net_ratio", "audjpy_oi_logchg", "available_utc"} <= set(tfx.columns)
    assert "usdjpy_contrarian_z" not in tfx.columns                 # 4 weeks < Z_MIN: none yet
    assert str(tfx["available_utc"].dt.tz) == "UTC"
    assert tfx.loc["2026-10-27", "available_utc"] == pd.Timestamp("2026-10-28 09:00", tz="UTC")
    jpx = J.footprint_frame("jpx_investor_type")
    assert jpx.loc["2026-10-25", "foreigners_net_bn"] == pytest.approx(30.398335)
    assert jpx.loc["2026-10-25", "available_utc"] == pd.Timestamp("2026-10-29 06:30", tz="UTC")
    ff = J.footprint_frame("ffaj_otc_fx")
    assert set(fp["ffaj_otc_fx"]["columns"]) <= set(ff.columns)
