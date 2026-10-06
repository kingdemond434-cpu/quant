"""alt_proxies, the physical exhaust (2026-10-06): China ports, freight, NBS power / FAI /
profits, CCGP award indices, Sentinel-5P NO2 and FIRMS over the named-facility registry, Naver
DataLab, the paid-vendor and refused-terms paths, the factory objects, the §2.5 sensor records
and the rent column.

Fixtures are SYNTHETIC pages in each publisher's documented layout; their numbers are
illustrative and never measured. Live yield of every source here is UNMEASURED.
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

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


def _parse(sid: str, ext: str, part: str = "") -> dict[tuple[str, date], A.Obs]:
    parse = A.BY_ID[sid].parse
    assert parse is not None
    obs = parse((FIX / f"{sid}.{ext}").read_bytes(), A.Ctx(part=part, fetched_at=NOW))
    return {(o.series, o.period): o for o in obs}


def _boom(url: str) -> tuple[bytes, str]:
    raise AssertionError(f"fetched {url}")


# ============================================================================ parsers
def test_mot_port_xlsx_reads_ports_and_derives_breadth_and_regional_gaps() -> None:
    got = _parse("cn_mot_port_monthly", "xlsx")
    aug = date(2026, 8, 31)
    assert got[("dalian_cargo_10kt", aug)].value == 3100.0
    assert got[("dalian_cargo_yoy", aug)].value == -3.0
    assert ("container_port_breadth", aug) in got
    assert got[("north_minus_south_cargo_yoy", aug)].value == pytest.approx(1.2406)
    assert ("bulk_minus_container_yoy", aug) in got


def test_scfi_routes_parse_current_and_previous_weeks() -> None:
    got = _parse("cn_sse_scfi_routes", "html")
    assert got[("scfi_composite", date(2026, 9, 25))].value == pytest.approx(1512.4)
    assert got[("scfi_composite", date(2026, 9, 18))].value == pytest.approx(1550.12)
    assert got[("shanghai__europe__usd_teu", date(2026, 9, 25))].value == 1650.0


def test_bls_deep_sea_freight_names_its_series() -> None:
    got = _parse("us_bls_deepsea_freight", "json")
    assert {s for s, _ in got} == {"deep_sea_freight_ppi"}
    assert len(got) == 56


def test_nbs_releases_carry_beijing_stamps_and_power_residual() -> None:
    ind = _parse("cn_nbs_industry_power", "html")
    aug = date(2026, 8, 31)
    assert ind[("crude_steel_yoy", aug)].value == -3.7
    assert ind[("thermal_power_yoy", aug)].value == -4.3
    assert ind[("crude_steel_yoy", aug)].published_at == datetime(2026, 9, 15, 2, tzinfo=UTC)
    assert any(s == "industrial_power_residual" for s, _ in ind)
    fai = _parse("cn_nbs_fai", "html")
    assert fai[("fai_ytd_yoy", aug)].value == -7.2 and fai[("infra_ytd_yoy", aug)].value == -4.0
    assert fai[("fai_mom", aug)].value == -0.5
    prof = _parse("cn_nbs_profits", "html")
    assert prof[("ferrous_smelting_profit_ytd_yoy", aug)].value == -62.4
    assert prof[("profit_ytd_yoy", aug)].published_at == datetime(2026, 9, 28, 1, 30, tzinfo=UTC)


def test_ccgp_award_count_is_keyed_by_basket_keyword_and_month() -> None:
    got = _parse("cn_ccgp_award_indices", "html", "steel:gangjiegou:2026-09")
    assert got[("steel__gangjiegou_awards", date(2026, 9, 30))].value == 1234.0
    items = A.ccgp_items((FIX / "cn_ccgp_award_indices.html").read_bytes())
    assert items and all(i["agency"] and "中标公告" not in i["agency"] for i in items)
    assert A.BY_ID["cn_ccgp_award_indices"].parse is not None
    assert A.parse_ccgp_awards(b"", A.Ctx(part="steel:gangjiegou:2026-09")) == []


def test_s5p_skips_cloudy_days_and_reads_named_facilities() -> None:
    got = _parse("cn_s5p_no2_clusters", "json", "tangshan")
    vals = {d: o.value for (s, d), o in got.items() if s == "tangshan_no2_umol"}
    shares = {d: o.value for (s, d), o in got.items() if s == "tangshan_no2_valid_share"}
    assert vals and set(vals) == set(shares) and min(shares.values()) >= 0.5


def test_naver_reads_ratio_to_the_anchor_at_week_end() -> None:
    got = _parse("kr_naver_datalab", "json")
    assert got and all(d.weekday() == 6 for _, d in got)     # weeks start Monday, dated Sunday


def test_facility_registry_is_cited_and_inside_china() -> None:
    reg = A.load_clusters()
    raw = json.loads((DESK / "data" / "industrial_clusters.json").read_text("utf-8"))
    assert len(reg) >= 20
    for f in raw["facilities"]:
        assert f["source"].startswith("https://") and f["types"], f["id"]
        assert 18.0 < f["lat"] < 54.0 and 73.0 < f["lon"] < 135.0, f["id"]
    areas = A.firms_areas()
    assert set(reg) <= set(areas)                   # FIRMS reads every registered facility


# ============================================================================ factory objects
def test_factory_features_use_a_strict_prefix() -> None:
    periods = [date(2023, 1, 31) + timedelta(days=31 * i) for i in range(40)]
    periods = [A._month_end(p.year, p.month) for p in periods]
    vals = [float(i % 12) + i * 0.1 for i in range(40)]
    base = A.factory_features(vals, periods, "monthly")
    alt = A.factory_features(vals[:30] + [v + 999 for v in vals[30:]], periods, "monthly")
    assert base[:30] == alt[:30]                                     # the future moves nothing
    p = base[30]
    assert p["delta"] == pytest.approx(vals[30] - vals[29])
    assert p["acceleration"] == pytest.approx((vals[30] - vals[29]) - (vals[29] - vals[28]))
    assert p["seasonal_basis"] == "same_period_prior_years"
    assert p["seasonal_expected"] == pytest.approx((vals[18] + vals[6]) / 2)
    assert p["percentile"] is not None and p["seasonal_z"] is not None


def test_breadth_counts_each_member_against_its_own_history() -> None:
    def pts(vals: list[float]) -> list[dict[str, Any]]:
        d0 = date(2026, 1, 1)
        return [{"d": (d0 + timedelta(days=i)).isoformat(), "value": v,
                 "published_time": "2026-01-01T00:00:00+00:00", "first_seen_at": None,
                 "published_basis": "release_rule"} for i, v in enumerate(vals)]
    per = {"a": pts([10.0] * 40 + [20.0] * 7), "b": pts([100.0] * 40 + [50.0] * 7)}
    rows = A.breadth_rows(per, ["a", "b"], "x")
    last = max(r["period"] for r in rows.values() if r["series"] == "x_breadth")
    assert rows[f"x_breadth|{last}"]["value_first"] == 0.5          # one up, one down


def test_sensor_records_carry_every_contract_field_and_revisions_as_their_own_rows() -> None:
    src = A.BY_ID["us_bls_deepsea_freight"]
    pts = {"deep_sea_freight_ppi": [{
        "d": "2026-08-31", "value": 10.0, "value_last": 11.0, "n_revisions": 1,
        "revision_time": "2026-10-01T13:00:00+00:00", "event_time": "2026-08-31",
        "published_time": "2026-09-21T13:00:00+00:00",
        "available_time": "2026-09-21T13:00:00+00:00",
        "first_seen_at": "2026-09-21T14:00:00+00:00", "vintage_id": "v1"}]}
    recs = A.sensor_records(src, pts)
    assert len(recs) == 2 and all(list(r) == list(A.SENSOR_FIELDS) for r in recs)
    first, rev = recs
    assert first["value"] == 10.0 and first["consensus"] is None
    assert rev["revision_of"] == first["observation_id"] and rev["revision_delta"] == 1.0
    assert rev["knowable_at"] == "2026-10-01T13:00:00+00:00"


def test_fixture_pass_writes_sensor_records_and_factory_columns(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "k-fixture")
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    assert rep["direct_cells"]["n"] == 0                     # fixtures never mint
    doc = json.loads((paths.sensor_dir / "us_bls_deepsea_freight.json").read_text("utf-8"))
    assert doc["fields"] == list(A.SENSOR_FIELDS) and doc["records"]
    lake = next(paths.series.glob("alt_us_bls_deepsea_freight__*.csv")).read_text("utf-8")
    for col in ("knowable_at", "delta", "acceleration", "seasonal_expected", "seasonal_z"):
        assert col in lake.splitlines()[0]


# ============================================================================ gates
def test_nse_option_chain_is_refused_on_terms_with_the_quoted_clause(tmp_path: Path) -> None:
    src = A.BY_ID["in_nse_option_chain"]
    assert src.terms == "refused" and A.status_of(src) == "BLOCKED_ON_TERMS:refused"
    ev = A.TERMS_EVIDENCE[src.id]
    assert "automated data collection" in ev["terms_quote"]
    assert A.NO_SUBSTITUTE[src.id]
    rec = A.collect(A.Paths(tmp_path / "desk"), src, {}, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=_boom)
    assert rec["requests"] == 0


@pytest.mark.parametrize("sid", ["cn_mot_port_monthly", "cn_sse_scfi_routes",
                                 "cn_ccgp_award_indices", "cn_samr_registrations",
                                 "kr_naver_datalab"])
def test_unconfirmed_physical_sources_are_never_fetched(sid: str, tmp_path: Path) -> None:
    src = A.BY_ID[sid]
    assert src.terms == "to_confirm" and A.status_of(src).startswith("BLOCKED+SUBSTITUTE:")
    rec = A.collect(A.Paths(tmp_path / "desk"), src, {}, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=_boom)
    assert rec["requests"] == 0


def test_tianyancha_is_unconfigured_paid_with_a_free_substitute(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TIANYANCHA_TOKEN", raising=False)
    src = A.BY_ID["cn_tianyancha_supply"]
    assert A.status_of(src) == "UNCONFIGURED+SUBSTITUTE:cn_nbs_profits"
    rec = A.collect(A.Paths(tmp_path / "desk"), src, {}, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=_boom)
    assert rec["requests"] == 0


def test_naver_needs_both_keys_and_s5p_needs_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    nav = A.Source(**{**A.BY_ID["kr_naver_datalab"].__dict__, "terms": "confirmed"})
    assert A.status_of(nav, {"NAVER_CLIENT_ID": "a"}) == "BLOCKED_ON_KEY:NAVER_CLIENT_SECRET"
    assert A.status_of(nav, {"NAVER_CLIENT_ID": "a", "NAVER_CLIENT_SECRET": "b"}) == \
        "UNMEASURED_LIVE_YIELD"
    s5p = A.BY_ID["cn_s5p_no2_clusters"]
    monkeypatch.setattr(A, "_token_helper", lambda: None)
    creds = {"CDSE_CLIENT_ID": "a", "CDSE_CLIENT_SECRET": "b"}
    assert A.status_of(s5p, creds) == "BLOCKED_ON_KEY:CDSE_TOKEN"    # no helper: token needed
    monkeypatch.setattr(A, "_token_helper", lambda: (lambda env: None))
    assert A.status_of(s5p, creds) == "UNMEASURED_LIVE_YIELD"        # helper mints from creds


def test_keys_never_reach_a_recorded_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NAVER_CLIENT_ID", "id-SECRET-1")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "sec-SECRET-2")
    src = A.BY_ID["kr_naver_datalab"]
    for r in A._naver_requests(src, NOW):
        assert "SECRET" not in r.url and "SECRET" not in A._redact(r.url, src)


def test_paid_vendors_are_listed_and_never_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    from research import asia_collector as C
    monkeypatch.setattr(C.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetched")))
    reg = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    rows = {s["id"]: s for s in reg["sources"]}
    for vid in ("rqdata", "wind"):
        assert rows[vid]["paid_blocked"] is True and vid in A.PAID_BLOCKED
        monkeypatch.setenv(str(rows[vid].get("key_env") or "RQDATA_FAKE"), "x")
        assert C.collect_one(rows[vid])["status"] == "PAID_BLOCKED"
    eng = json.loads((DESK / "data" / "paid_data_substitutes_asia_blocked.json")
                     .read_text("utf-8"))
    paid = {r["paid"].rsplit("[", 1)[1].rstrip("]"): r for r in eng["rows"]}
    assert paid["rqdata"]["status"] == paid["wind"]["status"] == "PAID_BLOCKED"


def test_rent_is_unmeasured_without_a_report_and_counted_with_one() -> None:
    r = A.rent_of("us_bls_deepsea_freight", 1)
    assert r["annual_cost_usd"] == 0 and r["survivors"] == A.UNMEASURED
    rep = {"gain_tests": {"us_bls_deepsea_freight|deep_sea_freight_ppi|XAUUSD":
                          {"verdict": "PASS"},
                          "us_bls_deepsea_freight|deep_sea_freight_ppi#seasonal_z|XAUUSD":
                          {"verdict": "FAIL"}}}
    r = A.rent_of("us_bls_deepsea_freight", 1, rep)
    assert r["cells_tested"] == 2 and r["survivors"] == 1 and r["cost_per_survivor_usd"] == 0
    assert A.rent_of("cn_tianyancha_supply", 0, rep)["cost_per_survivor_usd"] == A.UNMEASURED
    rows = {r["id"]: r for r in A.roster_file_rows()}
    assert rows["us_bls_deepsea_freight"]["rent"]["survivors"] == A.UNMEASURED


def test_new_physical_sources_map_only_to_mintable_universe_symbols() -> None:
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for s in A.PHYSICAL_SOURCES:
        src = A.BY_ID[s.id]
        for m in (src.instruments, *src.series_instruments.values()):
            assert set(m) <= set(uni) and set(m.values()) <= {1, -1}, src.id
            assert all(A.may_mint(sym) for sym in m), src.id
