"""The Japan official plane (asia directive PART IX, 2026-10-06).

MOF (weekly and by-investor securities flows, FX intervention record) and BOJ stat-search rows of
`alt_proxies` parse their documented wire formats into PIT series carrying the five alpha
objects; JPX, boj.or.jp HTML, J-Quants, TFX and the JGB auction .xls are lanes with no fetcher,
each with its verbatim terms; the Japan department runs on `global_research_os` and publishes
event objects and a funding state. Fixtures are SYNTHETIC values in the documented formats
(tests/fixtures/alt_proxies/README_jp_plane.md); nothing here is a measurement.
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
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
PLANE_IDS = tuple(s.id for s in A.JP_PLANE_SOURCES)
#: The codes the fixtures carry for the two rows that have no default code.
FIXTURE_CODES = {"ALT_BOJ_CA_DB": "BOJCA", "ALT_BOJ_CA_CODE": "SYNTHETIC_CA",
                 "ALT_BOJ_JGB_DB": "BS01", "ALT_BOJ_JGB_CODE": "SYNTHETIC_JGB"}


@pytest.fixture
def box_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in FIXTURE_CODES.items():
        monkeypatch.setenv(k, v)


def _obs(sid: str) -> list[A.Obs]:
    parse = A.BY_ID[sid].parse
    assert parse is not None
    body = sorted(FIX.glob(f"{sid}.*"))[0].read_bytes()
    return parse(body, A.Ctx(fetched_at=NOW))


# ---------------------------------------------------------------------------- parsing
def test_mof_weekly_reads_the_shift_jis_csv_and_dates_the_week_end() -> None:
    raw = (FIX / "jp_mof_securities_weekly.csv").read_bytes()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")                                  # the fixture is really cp932
    got = _obs("jp_mof_securities_weekly")
    periods = sorted({o.period for o in got})
    assert periods[0] == date(2025, 12, 6) and date(2026, 1, 3) in periods   # across the year
    assert all(p.weekday() == 5 for p in periods)                            # Saturdays
    row = {o.series: o.value for o in got if o.period == periods[0]}
    assert row["assets_total_net"] == pytest.approx(row["assets_equity_net"]
                                                    + row["assets_bonds_net"]
                                                    + row["assets_bills_net"])


def test_mof_investor_table_carries_the_year_forward() -> None:
    got = _obs("jp_mof_securities_investor_bonds")
    periods = {o.period for o in got}
    assert date(2025, 12, 31) in periods and date(2026, 7, 31) in periods
    assert not any(o.series.endswith("public_sector_net") and o.period.year < 2000 for o in got)
    assert "bonds_life_insurers_net" in {o.series for o in got}


def test_intervention_is_signed_from_the_yen_side() -> None:
    got = {o.period: o.value for o in _obs("jp_mof_fx_intervention")}
    assert got[date(2022, 9, 22)] == pytest.approx(28382)      # dollars sold, yen bought
    assert got[date(2011, 8, 4)] == pytest.approx(-45129)      # yen sold
    assert got[date(2022, 10, 24)] == pytest.approx(7296)      # continuation row, month carried
    assert got[date(2024, 5, 1)] == pytest.approx(38700)       # month changes mid-quarter
    assert len(got) == 8                                       # subtotal rows are not days


def test_boj_parser_reads_codes_frequencies_and_refuses_error_documents() -> None:
    call = _obs("jp_boj_call_rate")
    assert {o.series for o in call} == {"call_rate_on"} and call[0].period == date(2026, 7, 1)
    tk = _obs("jp_boj_tankan")
    assert min(o.period for o in tk) == date(2023, 3, 31)      # YYYYQQ quarterly -> quarter end
    err = b'{"STATUS":400,"MESSAGEID":"M181005E","MESSAGE":"invalid code"}'
    assert A.make_boj_parser({})(err, A.Ctx()) == []
    flat = json.dumps({"STATUS": 200, "RESULTSET": [{"SERIES_CODE": "X", "FREQUENCY": "MONTHLY",
                                                      "SURVEY_DATES": [202601], "VALUES": [1.5]}]})
    assert A.make_boj_parser({"X": "x"})(flat.encode(), A.Ctx())[0].period == date(2026, 1, 31)


def test_jquants_parser_reads_the_collector_output_with_its_published_date(tmp_path: Path) -> None:
    obs = A.parse_jquants_investor_types((FIX / "jp_jquants_investor_types.json").read_bytes(),
                                         A.Ctx())
    first = next(o for o in obs if o.series == "foreigners_net_kjpy")
    assert first.period == date(2026, 8, 7)
    assert first.published_at == datetime(2026, 8, 13, 7, tzinfo=UTC)
    assert {o.series for o in obs} == {"foreigners_net_kjpy", "individuals_net_kjpy",
                                       "trust_banks_net_kjpy"}                # Prime only
    v1 = json.dumps({"trades_spec": [{"PublishedDate": "2017-01-13", "EndDate": "2017-01-06",
                                       "Section": "TSE1st", "ForeignersBalance": 5}]})
    assert A.parse_jquants_investor_types(v1.encode(), A.Ctx())[0].value == 5
    paths = A.Paths(tmp_path / "desk")
    paths.private_series.mkdir(parents=True)              # the collector's PRIVATE store
    (paths.private_series / "jpx_jquants.json").write_bytes(
        (FIX / "jp_jquants_investor_types.json").read_bytes())
    assert len(A.read_jquants_investor_types(paths)) == len(obs)


# ---------------------------------------------------------------------------- PIT
def test_release_rules_are_late_biased() -> None:
    wk = A.BY_ID["jp_mof_securities_weekly"].rule(date(2026, 9, 26))        # Saturday
    assert wk == datetime(2026, 10, 1, tzinfo=UTC)          # Thursday 00:00 UTC > 23:50 Wed
    iv = A.BY_ID["jp_mof_fx_intervention"].rule(date(2026, 5, 6))
    assert iv >= datetime(2026, 8, 7, tzinfo=UTC)           # Q2 detail was published 08-07
    assert A.BY_ID["jp_boj_tankan"].rule(date(2026, 9, 30)) >= datetime(2026, 10, 1, tzinfo=UTC)
    for sid in PLANE_IDS:
        assert A.BY_ID[sid].rule(date(2026, 8, 27)) > datetime(2026, 8, 27, tzinfo=UTC), sid


# ---------------------------------------------------------------- Tokyo's calendar (#239's roll)
def test_jp_pack_derives_the_gazetted_holidays() -> None:
    from countries.jp import pack as P
    got = set(P.holidays(2026))
    for d in ("2026-01-12", "2026-05-06", "2026-09-21", "2026-09-22", "2026-09-23",
              "2026-11-23", "2026-12-31", "2026-01-02"):
        assert d in got, d
    assert {"2025-02-24", "2025-11-24"} <= set(P.holidays(2025))           # 振替休日
    assert {"2019-04-30", "2019-05-02", "2019-10-22"} <= set(P.holidays(2019))
    assert "2019-12-23" not in P.holidays(2019) and P.holidays(1999) == {}
    assert A.release_calendar_known("JP", 2005) and not A.release_calendar_known("JP", 1999)


#: (row, a period whose rule lands on a Tokyo closure, the instant weekends alone would give,
#:  the instant rolled past Tokyo's holidays). Each row is a BOJ/MOF daily, weekly or 10-daily row.
JP_ROLLS = (
    # Fri 18 Sep 2026 + 1 day = Sat -> Mon 21 (敬老の日), 22 (国民の休日), 23 (秋分) -> Thu 24
    ("jp_boj_call_rate", date(2026, 9, 18), datetime(2026, 9, 21, 3, tzinfo=UTC),
     datetime(2026, 9, 24, 3, tzinfo=UTC)),
    # Thu 17 Sep + 2 = Sat 19 -> Mon 21 .. Wed 23 closed -> Thu 24
    ("jp_boj_current_account", date(2026, 9, 17), datetime(2026, 9, 21, tzinfo=UTC),
     datetime(2026, 9, 24, tzinfo=UTC)),
    # 17 Sep + 4 = Mon 21 -> Thu 24
    ("jp_boj_jgb_holdings", date(2026, 9, 17), datetime(2026, 9, 21, tzinfo=UTC),
     datetime(2026, 9, 24, tzinfo=UTC)),
    # week to Sat 27 Dec 2025 + 5 = Thu 1 Jan -> 2 Jan (administrative closure) -> Mon 5 Jan
    ("jp_mof_securities_weekly", date(2025, 12, 27), datetime(2026, 1, 1, tzinfo=UTC),
     datetime(2026, 1, 5, tzinfo=UTC)),
)


@pytest.mark.parametrize(("sid", "period", "weekend_only", "rolled"), JP_ROLLS)
def test_boj_and_mof_rows_roll_past_tokyo_holidays(sid: str, period: date,
                                                   weekend_only: datetime,
                                                   rolled: datetime) -> None:
    src = A.BY_ID[sid]
    assert getattr(src.rule, "calendar", None) == "JP"
    assert A._roll_weekday(weekend_only) == weekend_only        # weekends alone stop here...
    assert src.rule(period) == rolled                          # ...Tokyo's calendar does not


def test_every_jp_plane_rule_rolls_on_tokyo_calendar() -> None:
    for sid in PLANE_IDS:
        assert getattr(A.BY_ID[sid].rule, "calendar", None) == "JP", sid


@pytest.mark.parametrize("sid", [r[0] for r in JP_ROLLS])
def test_jp_row_revisions_are_their_own_vintages(sid: str) -> None:
    """#239's per-revision stamping on each BOJ/MOF row: a revision is knowable only from the
    instant it was first seen (revision_points), and as_of before it returns the first print."""
    src = A.BY_ID[sid]
    series = src.signal_series[0]
    d = date(2026, 7, 31)
    seen1 = datetime(2026, 8, 20, tzinfo=UTC)
    seen2 = datetime(2026, 9, 15, 6, tzinfo=UTC)
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, [A.Obs(series, d, 100.0)], seen1)
    A.merge_vintages(store, src, [A.Obs(series, d, 104.0)], seen2)
    (row,) = store.values()
    assert row["value_first"] == 100.0 and row["vintages"][0]["seen_at"] == seen2.isoformat()
    (rev,) = A.revision_points(src, store)[series]
    assert rev["knowable_at"] == seen2.isoformat() and rev["revision_delta"] == 4.0
    assert rev["revision_of"] and rev["vintage_n"] == 1
    assert A.as_of(A.revision_points(src, store), seen2 - timedelta(seconds=1)) == {}
    assert A.as_of(A.revision_points(src, store), seen2)[series][0]["value"] == 104.0
    # the first print is stamped by the Tokyo-calendar rule, never before it
    assert row["published_time"] == src.rule(d).isoformat(timespec="seconds")


def test_points_carry_the_five_alpha_objects_and_revisions_are_vintages() -> None:
    src = A.BY_ID["jp_boj_call_rate"]
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, _obs(src.id), NOW)
    pts = A.build_points(src, store)["call_rate_on"]
    p2, p1 = pts[2], pts[1]
    assert p2["acceleration"] == pytest.approx(p2["delta"] - p1["delta"])
    assert all(k in p2 for k in ("knowable_at", "expected_value", "raw_surprise", "revision_of"))
    later = datetime(2026, 10, 2, tzinfo=UTC)
    A.merge_vintages(store, src, [A.Obs("call_rate_on", date(2026, 7, 1), 0.5)], later)
    rev = next(p for p in A.build_points(src, store)["call_rate_on"] if p["d"] == "2026-07-01")
    assert rev["value"] == pytest.approx(0.477) and rev["revision_delta"] == pytest.approx(0.023)


# ---------------------------------------------------------------------------- terms
def test_plane_rows_are_confirmed_with_evidence_and_blocked_hosts_are_not_sources() -> None:
    for sid in PLANE_IDS:
        assert A.BY_ID[sid].terms == "confirmed" and sid in A.JP_TERMS_EVIDENCE, sid
        ev = A.JP_TERMS_EVIDENCE[sid]
        assert ev["terms_url"].startswith("https://") and ev["terms_quote"]
        assert ev["checked_at"] == "2026-10-06"
    for sid, meta in A.JP_REFUSED.items():
        assert sid not in A.BY_ID                                  # no fetcher exists to run
        assert A.JP_TERMS_EVIDENCE[sid]["terms_quote"], sid
        assert meta["status"].startswith(("BLOCKED_ON_TERMS:", "UNCONFIGURED:")), sid
    assert A.JP_TERMS_EVIDENCE["jp_jpx_market_data"]["decision"] == "refused"
    # J-Quants left the refused lanes: it is a PRIVATE-USE lane under token_refresh's verdict.
    assert "jp_jquants_investor_types" not in A.JP_REFUSED
    jq = A.JP_PRIVATE_USE["jp_jquants_investor_types"]
    assert jq["depends_on"].startswith("PR #218") and jq["terms"] == "confirmed_private_use"
    assert A.JP_TERMS_EVIDENCE["jp_jquants_investor_types"]["decision"] == "confirmed_private_use"


def test_unconfigured_boj_codes_build_no_request(monkeypatch: pytest.MonkeyPatch) -> None:
    src = A.BY_ID["jp_boj_current_account"]
    for env in src.config_env:
        monkeypatch.delenv(env, raising=False)
    assert A.status_of(src) == "UNCONFIGURED:ALT_BOJ_CA_DB,ALT_BOJ_CA_CODE"
    assert A.requests_for(src, NOW, {}) == []
    (req,) = A.requests_for(A.BY_ID["jp_boj_call_rate"], NOW, {})
    assert "db=FM01" in req.url and "endDate=202609" in req.url and "{" not in req.url


# ---------------------------------------------------------------------------- cells
def test_plane_cells_route_through_the_lane_policy_and_name_their_data_source() -> None:
    from research import universe_policy
    gains: dict[str, dict[str, Any]] = {}
    for sid in PLANE_IDS:
        src = A.BY_ID[sid]
        assert ":" in A.data_source_of(src) and not A.data_source_of(src).startswith("alt_")
        for s in src.signal_series:
            for sym in src.instruments_for(s):
                assert not universe_policy.is_equity(sym), (sid, sym)
                assert A.may_mint(sym), (sid, sym)
                gains[f"{sid}|{s}|{sym}"] = {"verdict": "PASS", "ic": 0.2, "n": 50}
    cells = A.direct_cells(gains, NOW)
    assert cells and all(c["data_source"].split(":")[0] in ("mof", "boj") for c in cells)
    assert {c["data_source"] for c in cells} >= {"mof:fx_intervention", "boj:call_rate"}


def test_fixture_pass_publishes_axes_and_never_mints(tmp_path: Path, box_codes: None) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    assert rep["direct_cells"]["n"] == 0
    for sid in PLANE_IDS:
        axis = json.loads((paths.axes / f"alt_{sid}.json").read_text("utf-8"))
        assert any(k.split(".")[0] in A.BY_ID[sid].signal_series for k in axis["series"]), sid


# ---------------------------------------------------------------------------- department
def test_jp_plane_reports_lanes_events_and_funding_state(tmp_path: Path,
                                                         box_codes: None) -> None:
    from countries.jp import official_plane as J
    paths = A.Paths(tmp_path / "desk")
    A.run(paths, fixtures=FIX, donate=False, now=NOW)
    out = tmp_path / "JP.json"
    doc = J.run(paths=paths, report_default=out, now=NOW)
    assert json.loads(out.read_text("utf-8"))["country"] == "jp"
    lanes = {r["dataset"]: r for r in doc["lanes"]}
    for sid in PLANE_IDS:
        assert lanes[sid]["status"] == "PARSED", sid
        assert lanes[sid]["data_source"] == A.data_source_of(A.BY_ID[sid])
    assert lanes["jp_jpx_market_data"]["status"] == "BLOCKED_ON_TERMS:refused"
    jq = lanes["jp_jquants_investor_types"]
    assert jq["status"] == "PRIVATE_USE:UNMEASURED_LIVE_YIELD" and jq["observations"] == 0
    assert set(jq) <= set(J.JQ_PUBLIC_KEYS)
    assert lanes["jp_mof_jgb_auctions"]["status"] == "UNCONFIGURED:NEEDS_XLS_READER"
    kinds = {(e["event"], e["lifecycle"]) for e in doc["events"]}
    for k in (("jp_mof_intervention", "RELEASED"), ("jp_mof_intervention_monthly_total",
                                                      "SCHEDULED"),
              ("jp_boj_mpm", "RELEASED"), ("jp_boj_mpm", "SCHEDULED"),
              ("jp_boj_tankan", "RELEASED"), ("jp_mof_weekly_securities", "SCHEDULED")):
        assert k in kinds, k
    sides = {e["side"] for e in doc["events"] if e["event"] == "jp_mof_intervention"}
    assert sides == {"YEN_BUYING", "YEN_SELLING"}
    # the September 2026 meeting sits between call-rate prints in the fixture
    sep = next(e for e in doc["events"] if e["event"] == "jp_boj_mpm"
               and e["event_time"] == "2026-09-18")
    assert sep["lifecycle"] == "RELEASED"
    fs = doc["states"]["japan_funding_state"]
    assert fs["components"] and all(c["verdict"] in ("MEASURED", "UNMEASURED")
                                    for c in fs["components"])
    assert fs["yen_strength_z"] == "UNMEASURED" or isinstance(fs["yen_strength_z"], float)


def test_funding_state_with_nothing_measured_is_unmeasured_not_zero() -> None:
    from countries.jp import official_plane as J
    fs = J.funding_state({}, NOW)["japan_funding_state"]
    assert fs["yen_strength_z"] == "UNMEASURED" and fs["measured_components"] == 0


def test_global_research_os_runs_the_japan_department(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    from research import global_research_os as G
    assert "jp" in G.NON_LAB_PACKS                       # still not a lab pack
    miners, problem = G._load_extra("jp")
    assert problem == "" and "official_plane" in miners
    rows = G.department_rows(dry_run=True, codes=["jp"])
    (row,) = rows
    (disp,) = row["miner_dispositions"]
    assert disp["outcome"] == "RAN" and "lane(s)" in disp["why"], disp


def test_pack_names_a_department_that_exists() -> None:
    import importlib

    from countries.jp import pack
    mod = importlib.import_module(pack.DEPARTMENT_MODULE)
    assert callable(mod.run)


def test_refused_registry_rows_carry_the_terms_label() -> None:
    reg = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    rows = {r["id"]: r for r in reg["sources"]}
    for sid in ("jp_tocom_settlements", "jp_boj_decisions"):
        assert rows[sid]["access_label"] == "PUBLIC_WITH_TERMS" and rows[sid]["terms_note"]
