"""Fund-flow extension (ICI weekly MMF assets, TIC by country) and the jobs-postings nowcast
(BLS anchor, Adzuna doors, USAJOBS from alt_proxies). No network: the fixtures in
tests/fixtures/data_class_gap copy the layouts read on 2026-11-03 (the ICI 2021-04-08 release page,
the BLS v2 JSON shape, the Adzuna search response). Every live host was refused by the build
proxy, so live shape and liveness are UNMEASURED until the box runs the hunter.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from libs.research.access_classifier import ROUTING  # noqa: E402
from research import jobs_nowcast as J  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "data_class_gap"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
FAKE_KEY = "k3y-NOT-REAL-0123456789abcdef"
FAKE_ID = "id-NOT-REAL-42"


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "STORE", tmp_path / "world_datasets")
    monkeypatch.setattr(W, "OBS", tmp_path / "world_datasets" / "obs")
    monkeypatch.setattr(W, "KEYS", tmp_path / "world_datasets" / "keys.json")
    monkeypatch.setattr(W, "EXPOSURE", tmp_path / "world_datasets" / "exposure.json")
    monkeypatch.setattr(W, "DESK", tmp_path)
    monkeypatch.setattr(W, "MIN_REQUEST_GAP_S", 0.0)
    W._universe_at.cache_clear()
    return tmp_path


# ------------------------------------------------------------------------------- ICI ----
def test_ici_page_keeps_only_the_current_week_stamped_after_its_own_dateline():
    df = W._ici_mmf_frame(_fx("ici_mm_release.html"), {})
    got = dict(zip(df["series_code"], df["value"], strict=True))
    assert got["ici_mmf_total"] == 4484.48                   # the 4/7 column, never 3/31
    assert got["ici_mmf_government_institutional"] == 2723.75
    assert got["ici_mmf_total_retail"] == 1487.37
    assert len(got) == 12
    assert set(df["period"]) == {"2021-04-01"}               # period_end = Wed 2021-04-07
    assert {pd.Timestamp(x) for x in df["release_utc"]} == {_t("2021-04-09")}  # dateline + 1d


def test_ici_without_a_dateline_is_unparseable_never_zero():
    with pytest.raises(W.FetchError) as ei:
        W._ici_mmf_frame(b"<html><table><tr><td>Total</td><td>1</td></tr></table></html>", {})
    assert ei.value.reason == "unparseable"


def test_ici_release_days_are_thursdays_and_a_holiday_thursday_asks_wednesday():
    days = W.ici_release_days(datetime(2025, 12, 3, tzinfo=UTC))
    assert date(2025, 11, 26) in days                          # Thanksgiving 11-27 -> Wed
    assert all(d.weekday() == 3 for d in days if d != date(2025, 11, 26))
    door = W.ici_mmf_door(NOW)
    assert door["urls"][0]["url"].endswith("/mmf/mm_10_29_26")      # Thu before Tue 11-03
    assert len(door["urls_backfill"]) >= 104                     # weekly quality floor


def test_ici_is_mined_as_public_with_terms_research_only_and_never_redistributed():
    door = W.ici_mmf_door(NOW)
    assert tf.source_of_url(door["url"]) == "ici_stats"
    assert tf.input_source(door["url"]) is None                # a label, never a stop (5e)
    row = tf.SOURCE_POLICY["ici_stats"]
    assert row["access_label"] == "PUBLIC_WITH_TERMS" and row["research_only"] is True
    assert "personal use only" in row["terms"]["clauses"]["personal"]
    lab = W.access_labels("ici_stats")
    assert lab["redistribute_allowed"] is False
    assert "redistribute" not in ROUTING["PUBLIC_WITH_TERMS"]["allowed_uses"]
    doors = {r["door"]: r for r in W.terms_doors()}
    assert doors["ICI/MMF_WEEKLY"]["live_input"] == "PERMITTED"
    assert doors["ICI/MMF_WEEKLY"]["research_only"] is True


def test_an_unlisted_url_is_access_unclear_and_fails_closed():
    lab = W.access_labels(None)
    assert lab == {"access_label": "ACCESS_UNCLEAR", "redistribute_allowed": False,
                   "terms_note": ""}


# ------------------------------------------------------------------------------- BLS ----
def test_bls_keeps_months_drops_annual_and_dashes_and_stamps_the_shutdown_late():
    df = W._bls_api_frame(_fx("bls_jolts.json"), {})
    assert list(df["period"]) == ["2025-10", "2025-09", "2025-08"]
    assert set(df["series_code"]) == {"us_jolts_openings"}
    lag = dict(zip(df["period"], df["lag_days"], strict=True))
    assert lag["2025-09"] == 71 and lag["2025-08"] == 45      # released with Oct, 2025-12-09


def test_bls_refusal_is_named_never_a_zero():
    with pytest.raises(W.FetchError) as ei:
        W._bls_api_frame(_fx("bls_refused.json"), {})
    assert ei.value.reason == "api_refused"


def test_bls_door_reads_the_key_through_key_env_and_registers_it(store, monkeypatch):
    seen: list[str] = []
    registered: list[str] = []
    from libs.data import polite_fetch as pf
    monkeypatch.setattr(pf, "register_secret", lambda s: registered.append(s))
    monkeypatch.setenv("BLS_API_KEY", FAKE_KEY)
    spec = W.jobs_doors(NOW)[0]
    assert spec["key_env"] == "BLS_API_KEY" and "{api_key}" in spec["url"]
    assert tf.source_of_url(spec["url"]) == "us_bls_api"
    assert tf.input_source(spec["url"]) is None

    def fetch(url: str, timeout: float) -> bytes:
        seen.append(url)
        return _fx("bls_jolts.json")
    series = W._fetch_direct(W.Client(fetch, deadline=1e18), spec, NOW)
    assert FAKE_KEY in registered
    assert all("registrationkey=" + FAKE_KEY in u for u in seen)
    assert {s["code"] for s in series} == {"us_jolts_openings"}


def test_bls_without_a_key_is_needs_key_and_an_error_never_carries_the_key(store, monkeypatch):
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    spec = W.jobs_doors(NOW)[0]
    with pytest.raises(W.FetchError) as ei:
        W._fetch_direct(W.Client(lambda u, t: b"", deadline=1e18), spec, NOW)
    assert ei.value.reason == "needs_key"
    monkeypatch.setenv("BLS_API_KEY", FAKE_KEY)

    def boom(url: str, timeout: float) -> bytes:
        raise W.FetchError("http_500", url)
    with pytest.raises(W.FetchError) as ei:
        W._fetch_direct(W.Client(boom, deadline=1e18), {**spec, "urls": spec["urls"][:1]}, NOW)
    assert FAKE_KEY not in ei.value.detail and "{key}" in ei.value.detail


# ---------------------------------------------------------------------------- Adzuna ----
def test_adzuna_count_is_stamped_at_the_fetch_instant():
    df = W._adzuna_count_frame(_fx("adzuna_gb_count.json"),
                               {"series_code": "gb_postings_total",
                                "fetched_at": "2026-11-03T12:00:00Z"})
    r = df.iloc[0]
    assert r["value"] == 1012345.0 and r["period"] == "2026-11-03"
    assert pd.Timestamp(r["release_utc"]) == _t("2026-11-03T12:00")


def test_adzuna_is_held_with_a_missed_growth_line_and_reads_both_keys_by_name(store,
                                                                              monkeypatch):
    doors = [d for d in W.jobs_doors(NOW) if d["provider"] == "ADZUNA"]
    assert {d["dataset"] for d in doors} >= {f"POSTINGS_{c}" for c in
                                             ("US", "GB", "DE", "AU", "CA")}
    gb = next(d for d in doors if d["dataset"] == "POSTINGS_GB")
    assert gb["key_env"] == "ADZUNA_APP_KEY"
    assert gb["key_env_extra"] == {"{app_id}": "ADZUNA_APP_ID"}
    assert "GBPUSD" in gb["pin"] and "UK100" in gb["pin"]
    assert tf.input_source(gb["url"]) == "adzuna_api"           # HELD: contract on the key
    assert "aggregation" in tf.SOURCE_POLICY["adzuna_api"]["terms"]["clauses"]
    t = {r["door"]: r for r in W.terms_doors()}["ADZUNA/POSTINGS_GB"]
    assert t["live_input"] == "REFUSED"
    assert t["missed_growth"]["delta_elogw"] == "UNMEASURED" and t["missed_growth"]["unblock"]
    asked: list[str] = []
    cat = W._blank_catalog()
    stats: Counter[str] = Counter()
    monkeypatch.setattr(W, "direct_sources", lambda now=None: [gb])
    W.fetch_direct(W.Client(lambda u, t: asked.append(u) or b"", deadline=1e18), cat, now=NOW,
                   until=1e18, stats=stats, qstats=Counter(), by_provider={"ADZUNA": Counter()})
    assert asked == []                                          # never asked
    assert stats["direct:terms_ideas_only"] == 1
    live = W.door_liveness_report(cat)
    st = live["groups"]["jobs"]["doors"][0]
    assert st["state"] == "IDEAS_ONLY" and st["missed_growth"]["kind"] == "ideas_only_refusal"
    assert live["status"] == "OK"                               # a hold is not an empty run


# --------------------------------------------------------------------- liveness RED ----
def test_a_flow_door_goes_red_after_more_than_two_empty_runs(store, monkeypatch):
    door = W.ici_mmf_door(NOW) | {"liveness": "fund_flows"}
    monkeypatch.setattr(W, "direct_sources", lambda now=None: [door])
    cat = W._blank_catalog()

    def empty(url: str, timeout: float) -> bytes:
        raise W.FetchError("empty", url)
    for i in range(3):
        if i:
            cat["datasets"]["ICI/MMF_WEEKLY"]["next_due"] = None
        W.fetch_direct(W.Client(empty, deadline=1e18), cat, now=NOW, until=1e18,
                       stats=Counter(), qstats=Counter(), by_provider={"ICI": Counter()})
        rep = W.door_liveness_report(cat)
        if i < 2:
            assert rep["status"] == "OK", i
    assert rep["red_doors"] == ["ICI/MMF_WEEKLY"] and rep["status"].startswith("RED")


def test_every_flow_and_jobs_door_carries_liveness():
    doors = W.fund_flow_doors(NOW) + W.jobs_doors(NOW)
    assert all(d.get("liveness") in ("fund_flows", "jobs") for d in doors)


# ------------------------------------------------------------------------- nowcast ----
def _t(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def test_nowcast_index_and_surprise_are_causal_and_use_the_last_known_print():
    post = [(_t(f"2025-09-{d:02d}"), _t(f"2025-09-{d:02d}T13:00"), 100.0) for d in (2, 9, 16, 23)]
    post += [(_t("2025-11-20"), _t("2025-11-20T13:00"), 110.0),
             (_t("2025-12-10"), _t("2025-12-10T13:00"), 120.0)]
    # JOLTS 2025-08 known 2025-09-30, 2025-09 known only 2025-12-09 (the shutdown)
    anchor = [(_t("2025-08-31"), _t("2025-09-30"), 7227.0),
              (_t("2025-09-30"), _t("2025-12-09T15:00"), 7658.0)]
    out = J.nowcast(post, anchor)
    idx = {e.date().isoformat(): v for e, _, v in out["index"]}
    assert "2025-09-16" not in idx and idx["2025-09-23"] == pytest.approx(100.0)
    sur = {e.date().isoformat(): (a, v) for e, a, v in out["surprise"]}
    # on 11-20 the last known print is AUGUST and there are no August postings: no point
    assert "2025-11-20" not in sur
    a, v = sur["2025-12-10"]
    assert v == pytest.approx(20.0)                    # 120 vs September's mean of 100
    assert a == _t("2025-12-10T13:00")
    imp = {e.date().isoformat(): v for e, _, v in out["implied"]}
    assert imp["2025-12-10"] == pytest.approx(7658.0 * 1.2)
    for _e, a, _ in out["surprise"]:
        assert a >= _t("2025-12-09T15:00")             # never before the print it uses


def test_nowcast_reaches_the_cell_path_for_the_pinned_fx_pair_and_index(store, monkeypatch):
    monkeypatch.setattr(W, "UNIVERSE", ROOT / "desks" / "mt5" / "data" / "universe" /
                        "universe.json")
    W._universe_at.cache_clear()
    axes = store / "data" / "axes"
    axes.mkdir(parents=True)
    days = pd.date_range("2026-01-01", "2026-11-02", freq="D")
    pts = [{"d": d.date().isoformat(), "v": 1000.0 + (i % 17),
            "available_time": f"{d.date().isoformat()}T14:00"} for i, d in enumerate(days)]
    (axes / J.USAJOBS_AXIS).write_text(json.dumps(
        {"series": {J.USAJOBS_SERIES: {"points": pts}}}), encoding="utf-8")
    bls = W.series_from_long(W._bls_api_frame(_fx("bls_jolts.json"), {}), freq="monthly")
    W.ingest_series("BLS", "JOLTS_CES", "jolts", bls, now=NOW, base_score=1.0,
                    declared_lag=45, qstats=Counter(), pin_instruments=W.JOBS_PINS["us"])
    rep = J.ingest(NOW, Counter())
    assert rep["us"]["source"] == "usajobs_federal"
    assert isinstance(rep["us"]["index_points"], int)
    assert rep["gb"]["index"] == J.UNMEASURED                       # Adzuna held: no data
    frame = pd.read_parquet(W.dataset_path(J.PROVIDER, "US"))
    assert "us_postings_index" in set(frame["series_code"])
    first = frame[(frame.series_code == "us_postings_index")].sort_values("period").iloc[0]
    assert first["available_time"] == _t("2026-01-04T14:00")       # its 4th input, not period
    meta = json.loads(W.meta_path(J.PROVIDER, "US").read_text(encoding="utf-8"))
    insts = meta["series"]["us_postings_index"]["instruments"]
    assert "US500" in insts and "EURUSD" in insts
    W.build_exposure(NOW)
    exp = json.loads(W.EXPOSURE.read_text(encoding="utf-8"))
    key = W.series_key(J.PROVIDER, "US", "us_postings_index")
    assert key in exp["symbols"]["US500"] and key in exp["symbols"]["EURUSD"]
    s = W.raw_world_series(key)
    assert s is not None and len(s) >= 250


def test_mof_weekly_reaches_jpy_and_jpn225():
    uni = W._universe_at(str(ROOT / "desks" / "mt5" / "data" / "universe" / "universe.json"), 0)
    door = next(d for d in W.fund_flow_doors(NOW) if d["provider"] == "JP_MOF")
    insts = W.instruments_for(door["currencies"], door.get("stems", ()), uni)
    assert "USDJPY" in insts and "JPN225" in insts
