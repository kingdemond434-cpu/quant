"""domain_factories (DATA-43 / DATA-25): degree-day math, forecast revisions and model
disagreement, PIT stamping through alt_proxies' vintage store, hypothesis minting in the shape the
compiler admits, HELD sources never fetched, NEEDS_KEY when a key is absent, and one fixture pass.

Fixtures under tests/fixtures/domain_factories are SYNTHETIC files shaped like each publisher's
(CPC degree-day text, GFSX MOS bulletins, NWS API JSON, Indeed CSV, BLS JSON, ORNL TESViS JSON);
the numbers are illustrative and never measured. No test touches the network.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402
from research import domain_factories as D  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "domain_factories"
NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


class Recorder:
    """A getter that serves fixtures and records every request it was asked to make."""

    def __init__(self, root: Path = FIX) -> None:
        self.reqs: list[D.Req] = []
        self.inner = D.fixture_getter(root)

    def __call__(self, req: D.Req) -> bytes:
        self.reqs.append(req)
        return self.inner(req)

    def hosts(self) -> set[str]:
        from urllib.parse import urlparse
        return {urlparse(r.url).hostname or "" for r in self.reqs}


# ============================================================================ degree-day math
def test_hdd_cdd_base_65f() -> None:
    assert D.hdd(50.0) == 15.0
    assert D.hdd(70.0) == 0.0
    assert D.cdd(80.0) == 15.0
    assert D.cdd(60.0) == 0.0
    assert D.degree_days(40, 60, "hdd") == 15.0      # mean 50 F
    assert D.degree_days(70, 90, "cdd") == 15.0      # mean 80 F
    assert D.degree_days(60, 70, "hdd") == 0.0       # mean 65 F: neither
    assert D.degree_days(60, 70, "cdd") == 0.0


def test_hdd_cdd_base_18c() -> None:
    assert D.hdd_c(10.0) == 8.0
    assert D.hdd_c(20.0) == 0.0
    assert D.cdd_c(25.5) == pytest.approx(7.5)
    assert D.BASE_C == 18.0 and D.BASE_F == 65.0


# ============================================================================ parsers
def test_mex_parses_nx_pairs_skips_missing_and_rolls_the_month() -> None:
    rows = D.parse_mex((FIX / "feus21.kwno.mex.ne1.txt").read_bytes())
    bos = {r["target"]: r for r in rows if r["station"] == "KBOS"}
    assert bos["2026-10-07"]["tmin"] == 38 and bos["2026-10-07"]["tmax"] == 58
    assert "2026-10-12" not in bos                     # 999 is missing, never a temperature
    assert len(bos) == 6
    assert {r["issued_at"] for r in rows} == {"2026-10-06T12:00:00+00:00"}
    xn = D.parse_mex((FIX / "feus22.kwno.mex.se1.txt").read_bytes())
    atl = {r["target"]: r for r in xn}
    assert atl["2026-10-31"]["tmax"] == 70 and atl["2026-10-31"]["tmin"] == 50   # X/N order
    assert atl["2026-11-01"]["tmax"] == 72                                      # month rolls


def test_cpc_parses_regions_and_skips_blank_cells() -> None:
    got = D.parse_cpc((FIX / "cpc_2026_Heating.txt").read_bytes())
    assert set(got) == {*map(str, range(1, 10)), "CONUS"}
    assert got["1"]["20260101"] == 31.0
    assert "20260105" not in got["9"]                  # blank cell is missing, not zero


def test_nws_forecast_pairs_day_max_with_that_nights_min() -> None:
    rows = D.parse_nws_forecast((FIX / "nws_forecast_KBOS.json").read_bytes(), "KBOS")
    by = {r["target"]: r for r in rows}
    assert by["2026-10-07"]["tmax"] == 60 and by["2026-10-07"]["tmin"] == 40
    assert "2026-10-09" not in by                      # no night period: not a day
    assert rows[0]["issued_at"] == "2026-10-06T15:02:11+00:00"   # generatedAt is the vintage
    assert D.parse_nws_points((FIX / "nws_points_KBOS.json").read_bytes()) == {
        "office": "BOX", "x": 71, "y": 90}


# ============================================================================ revisions
def _run(model: str, st: str, issued: datetime, temps: dict[str, tuple[float, float]],
         seen: datetime | None = None) -> list[dict[str, Any]]:
    return [{"model": model, "station": st, "issued_at": issued.isoformat(timespec="seconds"),
             "target": t, "tmin": lo, "tmax": hi} for t, (lo, hi) in temps.items()]


def _store(*runs: tuple[list[dict[str, Any]], datetime]) -> dict[str, Any]:
    s: dict[str, Any] = {}
    for rows, seen in runs:
        D.merge_forecasts(s, rows, seen)
    return s


def test_revision_is_latest_minus_the_run_at_least_20h_older_same_target() -> None:
    t0 = datetime(2026, 10, 5, 12, tzinfo=UTC)
    tgt = {"2026-10-08": (40.0, 50.0), "2026-10-09": (40.0, 60.0)}     # HDD 20, 15
    cold = {"2026-10-08": (30.0, 40.0), "2026-10-09": (40.0, 60.0)}    # HDD 30, 15
    mid = {"2026-10-08": (0.0, 0.0), "2026-10-09": (0.0, 0.0)}         # 6 h later: never "prev"
    s = _store((_run("gfs_mos", "KBOS", t0, tgt), t0 + timedelta(hours=4)),
               (_run("gfs_mos", "KBOS", t0 + timedelta(hours=18), mid),
                t0 + timedelta(hours=22)),
               (_run("gfs_mos", "KBOS", t0 + timedelta(hours=24), cold),
                t0 + timedelta(hours=28)))
    rev = D.revisions(s, "gfs_mos", t0 + timedelta(hours=30), "hdd")
    assert rev["KBOS"] == {"2026-10-08": 10.0, "2026-10-09": 0.0}
    # A run this box had not yet SEEN is not the latest: PIT on first_seen_at.
    early = D.revisions(s, "gfs_mos", t0 + timedelta(hours=25), "hdd")
    assert early == {}               # latest seen is the 18 h run: no run >= 20 h before it


def test_every_vintage_is_kept_and_never_overwritten() -> None:
    t0 = datetime(2026, 10, 5, 12, tzinfo=UTC)
    s = _store((_run("gfs_mos", "KBOS", t0, {"2026-10-08": (40.0, 50.0)}), t0))
    again = D.merge_forecasts(s, _run("gfs_mos", "KBOS", t0, {"2026-10-08": (0.0, 0.0)}),
                              t0 + timedelta(hours=1))
    assert again == 0
    (row,) = s.values()
    assert row["tmin"] == 40.0 and row["first_seen_at"] == t0.isoformat(timespec="seconds")


def test_disagreement_needs_both_models_within_24h() -> None:
    t0 = datetime(2026, 10, 6, 12, tzinfo=UTC)
    s = _store((_run("gfs_mos", "KBOS", t0, {"2026-10-08": (30.0, 40.0)}), t0),
               (_run("nws_ndfd", "KBOS", t0 + timedelta(hours=3), {"2026-10-08": (40.0, 50.0)}),
                t0 + timedelta(hours=3)),
               (_run("gfs_mos", "KLGA", t0, {"2026-10-08": (30.0, 40.0)}), t0),
               (_run("nws_ndfd", "KLGA", t0 - timedelta(hours=30), {"2026-10-08": (40.0, 50.0)}),
                t0 - timedelta(hours=30)))
    dis = D.disagreement(s, t0 + timedelta(hours=4), "hdd")
    assert dis == {"KBOS": {"2026-10-08": 10.0}}       # 30 - 20; KLGA runs 30 h apart


def test_conus_aggregate_is_population_weighted_and_refuses_partial_coverage() -> None:
    per = {"KBOS": {"t": 10.0}, "KBDL": {"t": 20.0}}                    # div 1 mean 15
    assert D.aggregate(per, "div1") == {"t": 15.0}
    assert D.aggregate(per, "conus") == {}                              # 1 of 9 divisions
    one_per_div = {"KBOS": 1.0, "KLGA": 2.0, "KORD": 3.0, "KMSP": 4.0, "KATL": 5.0,
                   "KBNA": 6.0, "KDFW": 7.0, "KDEN": 8.0, "KLAX": 9.0}
    got = D.aggregate({k: {"t": v} for k, v in one_per_div.items()}, "conus")["t"]
    w = D.DIVISION_WEIGHTS
    assert got == pytest.approx(sum(w[n] * n for n in w) / sum(w.values()))


def test_forecast_metrics_week_level_revision_and_disagreement() -> None:
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    t_prev, t_last = now - timedelta(hours=30), now - timedelta(hours=6)
    days = [(now.date() + timedelta(days=k)).isoformat() for k in range(1, 8)]
    sts = ("KBOS", "KLGA", "KORD", "KMSP", "KATL", "KBNA", "KDFW", "KDEN", "KLAX")
    runs = []
    for st in sts:
        runs.append((_run("gfs_mos", st, t_prev, dict.fromkeys(days, (45.0, 55.0))), t_prev))
        runs.append((_run("gfs_mos", st, t_last, dict.fromkeys(days, (40.0, 50.0))), t_last))
        runs.append((_run("nws_ndfd", st, t_last, dict.fromkeys(days, (44.0, 54.0))), t_last))
    m = D.forecast_metrics(_store(*runs), now)
    assert m["conus_hdd_fcst_wk"] == pytest.approx(7 * 20.0)            # HDD 20 a day
    assert m["conus_hdd_rev_wk"] == pytest.approx(6 * 5.0)              # 5 colder, 6 days
    assert m["conus_hdd_dis_wk"] == pytest.approx(6 * 4.0)              # MOS 4 colder than NDFD
    assert m["div1_hdd_rev_wk"] == pytest.approx(30.0)
    assert m["conus_cdd_fcst_wk"] == 0.0


# ============================================================================ observed anomaly
def test_anomaly7_against_prior_years_same_window() -> None:
    ser: dict[date, float] = {}
    for y in range(2016, 2027):
        for k in range(10):
            ser[date(y, 1, 1) + timedelta(days=k)] = 20.0 if y < 2026 else 30.0
    assert D.anomaly7(ser, date(2026, 1, 8)) == pytest.approx(70.0)     # 210 - 140
    assert D.anomaly7(ser, date(2026, 1, 3)) is None                    # window incomplete
    assert D.anomaly7({k: v for k, v in ser.items() if k.year >= 2025},
                      date(2026, 1, 8)) is None                         # one prior year < 3


def test_observed_anomaly_waits_for_the_full_normal() -> None:
    cpc = {"hdd": D.parse_cpc((FIX / "cpc_2026_Heating.txt").read_bytes()), "cdd": {}}
    obs = D.observed_obs(cpc, date(2026, 1, 21), normals_ready=False)
    assert {o.series for o in obs} == {"conus_hdd"}
    assert len(obs) == 20


# ============================================================================ PIT stamping
def test_pit_forecast_obs_stamped_at_fetch_and_observed_by_release_rule(tmp_path: Path) -> None:
    p = D.Paths(tmp_path)
    D.merge_into(p, D.WEATHER_FCST, [A.Obs("conus_hdd_rev_wk", NOW.date(), 12.5,
                                           published_at=NOW)], NOW)
    pts = D.publish(p, D.WEATHER_FCST, NOW, dry_run=False)["conus_hdd_rev_wk"]
    assert pts[0]["available_time"] == NOW.isoformat(timespec="seconds")
    assert pts[0]["first_seen_at"] == NOW.isoformat(timespec="seconds")
    d = date(2026, 10, 5)
    D.merge_into(p, D.WEATHER_OBS, [A.Obs("conus_hdd", d, 4.0)], NOW)
    later = NOW + timedelta(hours=1)
    res = D.merge_into(p, D.WEATHER_OBS, [A.Obs("conus_hdd", d, 6.0)], later)
    assert res == {"added": 0, "revised": 1}
    pts = D.publish(p, D.WEATHER_OBS, NOW, dry_run=False)["conus_hdd"]
    assert pts[0]["value"] == 4.0                          # the first vintage is the value
    assert pts[0]["revision_time"] == later.isoformat(timespec="seconds")
    assert pts[0]["available_time"] == "2026-10-06T18:00:00+00:00"     # D+1 18:00 UTC
    lake = tmp_path / "data" / "lake" / "series" / "alt_dfw_weather_obs__conus_hdd.csv"
    assert lake.exists() and "available_time" in lake.read_text().splitlines()[0]


def test_indeed_fresh_rows_stamped_at_fetch_history_by_rule() -> None:
    now = datetime(2026, 10, 1, 12, tzinfo=UTC)
    got = D.parse_indeed_aggregate((FIX / "indeed_aggregate_US.csv").read_bytes(), now)
    assert {(o.series, o.period) for o in got} == {
        ("US_total_sa", date(2026, 9, 28)), ("US_total_sa", date(2026, 9, 29)),
        ("US_new_sa", date(2026, 9, 29))}               # 2020 row older than the kept window
    assert all(o.published_at == now for o in got)
    old = D.parse_indeed_aggregate((FIX / "indeed_aggregate_US.csv").read_bytes(),
                                   datetime(2026, 12, 31, tzinfo=UTC))
    assert all(o.published_at is None for o in old)
    sec = D.parse_indeed_sector((FIX / "indeed_sector_US.csv").read_bytes(), now)
    assert {o.period.weekday() for o in sec} == {4}      # Fridays only
    assert {o.series for o in sec} == {"US_sector_software_development", "US_sector_construction"}


def test_ndvi_parses_valid_pixels_and_stamps_at_processing_date() -> None:
    (o,) = D.parse_ornl((FIX / "ornl_us_corn_belt_ia.json").read_bytes(), "us_corn_belt_ia")
    assert o.value == pytest.approx(sum([8000, 8200, 7800, 8100, 8000, 7900, 8300, 8100]) / 8
                                    * 1e-4)
    assert o.period == date(2026, 7, 11)                # composite end
    assert o.published_at == datetime(2026, 7, 13, 3, 15, tzinfo=UTC)


def test_ndvi_anomaly_against_same_window_prior_years() -> None:
    store: dict[str, Any] = {}
    obs = [A.Obs("r_ndvi", date(y, 7, 11), 0.6 if y < 2026 else 0.8,
                 published_at=datetime(y, 7, 20, tzinfo=UTC)) for y in (2023, 2024, 2025, 2026)]
    A.merge_vintages(store, D.NDVI, obs, NOW)
    an = {o.period.year: o for o in D.ndvi_anomalies(store)}
    assert an[2026].value == pytest.approx(0.2)
    assert an[2026].published_at == datetime(2026, 7, 20, tzinfo=UTC)
    assert 2023 not in an and 2024 not in an           # fewer than two prior years


def test_bls_reads_monthly_rows_and_drops_annual() -> None:
    got = D.parse_bls((FIX / "bls_JTS000000000000000JOL.json").read_bytes())
    assert [(o.period, o.value) for o in got] == [(date(2026, 8, 31), 7227.0),
                                                  (date(2026, 7, 31), 7181.0)]


# ============================================================================ terms and keys
def test_held_sources_never_build_or_send_a_request(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("USAJOBS_API_KEY", "USAJOBS_USER_AGENT", "ADZUNA_APP_KEY", "ADZUNA_APP_ID"):
        monkeypatch.setenv(k, "x")                     # even with keys present
    rec = Recorder()
    rep = D.run(D.Paths(tmp_path), fixtures=FIX, getter=rec, now=NOW, donate=False)
    jobs = rep["factories"]["jobs"]["sources"]
    assert jobs["usajobs"]["status"] == D.HELD and jobs["adzuna"]["status"] == D.HELD
    assert rep["factories"]["weather"]["sources"]["open_meteo"]["status"] == D.HELD
    hosts = rec.hosts()
    assert not any(h.endswith(("usajobs.gov", "adzuna.com", "adzuna.co.uk", "open-meteo.com",
                               "ecmwf.int")) for h in hosts)
    assert {r.source for r in rec.reqs} <= {k for k, t in D.TERMS_RECORDS.items() if t.permits}
    with pytest.raises(D.HeldSource):
        D.guarded_get(D.Req("usajobs", "https://data.usajobs.gov/api/search", "x"), rec)
    with pytest.raises(D.HeldSource):
        D.guarded_get(D.Req("open_meteo", "https://api.open-meteo.com/v1/forecast", "x"), rec)


def test_every_permitted_source_carries_a_verbatim_quote() -> None:
    for sid, t in D.TERMS_RECORDS.items():
        if t.verdict == "PERMITS":
            assert t.terms_quote.strip() and t.terms_url.startswith("https://"), sid
    assert not D.TERMS_RECORDS["usajobs"].permits
    assert D.TERMS_RECORDS["adzuna"].verdict == "PROHIBITS"


def test_needs_key_when_bls_key_absent_and_nothing_requested(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    rec = Recorder()
    rep = D.run(D.Paths(tmp_path), fixtures=FIX, getter=rec, now=NOW, donate=False)
    bls = rep["factories"]["jobs"]["sources"]["bls_jolts"]
    assert bls["status"] == D.NEEDS_KEY and bls["key_state"] == "NEEDS_KEY:BLS_API_KEY"
    assert bls["requests"] == 0 and "api.bls.gov" not in rec.hosts()
    adz = rep["factories"]["jobs"]["sources"]["adzuna"]
    assert adz["status"] == D.HELD and "ADZUNA_APP_ID" in adz["key_state"]


def test_bls_key_is_never_written_to_the_report(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLS_API_KEY", "sekret-key-123")

    def boom(req: D.Req) -> bytes:
        if "api.bls.gov" in req.url:
            raise OSError(f"failed {req.url}")
        return D.fixture_getter(FIX)(req)
    rep = D.run(D.Paths(tmp_path), fixtures=FIX, getter=boom, now=NOW, donate=False)
    text = json.dumps(rep) + (tmp_path / "reports" / "DOMAIN_FACTORIES.json").read_text()
    assert "sekret-key-123" not in text
    assert "<BLS_API_KEY>" in text


# ============================================================================ minting
def _lake_points(n: int) -> list[dict[str, Any]]:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    return [{"d": (t0 + timedelta(days=i)).date().isoformat(),
             "event_time": (t0 + timedelta(days=i)).date().isoformat(),
             "available_time": (t0 + timedelta(days=i, hours=18)).isoformat(),
             "value": float(i % 7), "pace": None, "pit_quality": "live"} for i in range(n)]


def test_hypothesis_minted_only_with_enough_points_in_the_compiler_shape() -> None:
    state: dict[str, Any] = {}
    srcs = {s.id: s for s in (D.WEATHER_OBS, D.WEATHER_FCST)}
    few = {"dfw_weather_obs": {"conus_hdd_anom7": _lake_points(D.MIN_POINTS - 1)}}
    rows, held = D._hyp_rows(D.DEFAULT_PATHS, D.WEATHER_HYPS[:1], srcs, few, "weather", state,
                             NOW)
    assert rows == [] and held[0]["why"].startswith("UNMEASURED")
    enough = {"dfw_weather_obs": {"conus_hdd_anom7": _lake_points(40)}}
    rows, held = D._hyp_rows(D.DEFAULT_PATHS, D.WEATHER_HYPS[:3], srcs, enough, "weather",
                             state, NOW)
    assert [r["symbol"] for r in rows] == ["XNGUSD", "XTIUSD", "XBRUSD"]
    r = rows[0]
    assert r["family"] == "exogenous_conditioner" and r["kind"] == "hypothesis"
    assert r["params"]["source"] == "alt_dfw_weather_obs__conus_hdd_anom7"
    assert r["params"]["side_when_high"] == 1 and r["params"]["transform"] == "level_z"
    assert r["available_time"] == _lake_points(40)[-1]["available_time"]
    assert r["evidence"]["tested_here"] is False
    from research.miner_candidate_compiler import compile_row
    cands, disp = compile_row(D.ORGAN, r, {"XNGUSD"})
    assert disp == "EXACT_RECIPE" and cands[0]["family"] == "exogenous_conditioner"
    assert cands[0]["params"]["source"] == r["params"]["source"]


def test_minted_cells_are_not_redonated_within_the_window() -> None:
    srcs = {s.id: s for s in (D.WEATHER_OBS, D.WEATHER_FCST)}
    pts = {"dfw_weather_obs": {"conus_hdd_anom7": _lake_points(40)}}
    state: dict[str, Any] = {"minted": {}}
    rows, _ = D._hyp_rows(D.DEFAULT_PATHS, D.WEATHER_HYPS[:1], srcs, pts, "weather", state, NOW)
    state["minted"][rows[0]["cell"]] = NOW.isoformat()
    again, held = D._hyp_rows(D.DEFAULT_PATHS, D.WEATHER_HYPS[:1], srcs, pts, "weather", state,
                              NOW + timedelta(days=1))
    assert again == [] and held[0]["why"].startswith("already donated")


def test_payments_take_only_permitted_components_at_their_own_release() -> None:
    avail = "2026-09-10T00:00:00+00:00"
    alt = {"us_oi_card_spend": {"spend_all": [{"d": "2026-08-31", "pace": 2.5,
                                               "available_time": avail}]},
           "tr_bkm_card": {"card": [{"d": "2026-08-31", "pace": 9.9, "available_time": avail}]}}
    got = D.payment_obs(alt, ["us_oi_card_spend"])
    assert [(o.series, o.value) for o in got] == [("US_payments", 2.5)]
    assert got[0].published_at == datetime(2026, 9, 10, tzinfo=UTC)
    assert D.payment_obs(alt, []) == []


def test_refused_payment_sources_report_held(tmp_path: Path) -> None:
    runs = {sid: D._alt_run(D.Paths(tmp_path), sid)
            for sid in ("in_npci_upi", "tr_bkm_card", "br_cielo_icva", "za_beti",
                        "cn_holiday_spend", "kr_bok_card_spend")}
    assert {r.status for r in runs.values()} == {D.HELD}
    assert D._alt_run(D.Paths(tmp_path), "br_bcb_payments").status == D.UNMEASURED  # empty store


# ============================================================================ one fixture pass
def test_fixture_pass_writes_the_report_series_and_statuses(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch
                                                           ) -> None:
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    donated: list[list[dict[str, Any]]] = []

    def donor(rows: list[dict[str, Any]]) -> dict[str, Any]:
        donated.append(rows)
        return {"donated": len(rows), "path": "x"}
    rep = D.run(D.Paths(tmp_path), fixtures=FIX, now=NOW, donor=donor)
    w = rep["factories"]["weather"]["sources"]
    assert w["cpc_degree_days"]["status"] == D.FETCHED
    assert w["nws_mex_mos"]["status"] == D.FETCHED
    assert w["nws_api_ndfd"]["status"] == D.FETCHED
    assert w["ecmwf_open_data"]["status"] == D.UNMEASURED and w["ecmwf_open_data"]["requests"] == 0
    assert rep["factories"]["jobs"]["sources"]["indeed_hiring_lab"]["status"] == D.FETCHED
    assert rep["factories"]["ndvi"]["sources"]["ornl_modis_ndvi"]["status"] == D.FETCHED
    assert set(rep["status_counts"]) == set(D.STATUSES)
    assert set(rep["domains"]) == set(D.ALT_DOMAINS)
    vint = json.loads((tmp_path / "data" / "domain_factories" /
                       "weather_forecast_vintages.json").read_text())
    assert {r["model"] for r in vint.values()} == {"gfs_mos", "nws_ndfd"}
    report = json.loads((tmp_path / "reports" / "DOMAIN_FACTORIES.json").read_text())
    assert report["organ"] == "domain_factories"
    assert (tmp_path / "data" / "lake" / "series" / "alt_dfw_weather_obs__conus_hdd.csv").exists()
    # Too little history for any hypothesis: each is held back with the reason, none donated.
    assert rep["hypotheses"]["built"] == 0 and donated == []
    held = rep["factories"]["weather"]["held_back"]
    assert held and all(h["why"].startswith("UNMEASURED") for h in held)


def test_dry_run_writes_only_the_report(tmp_path: Path) -> None:
    D.run(D.Paths(tmp_path), fixtures=FIX, now=NOW, dry_run=True)
    assert (tmp_path / "reports" / "DOMAIN_FACTORIES.json").exists()
    assert not (tmp_path / "data" / "domain_factories" / "obs").exists()
    assert not (tmp_path / "data" / "lake").exists()
