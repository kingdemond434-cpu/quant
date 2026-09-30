"""alt_proxies, paid-substitute sources: GDELT's slot accumulator and cursors, every new parser
against its fixture, the per-date request cursor, the new transforms, the agreement metric and
the roster rows (repo file and in-code) for the RavenPack / card / foot-traffic / satellite
substitutes.

Fixtures are SYNTHETIC pages shaped like each publisher's, except `us_oi_card_spend.csv` and
`us_oi_google_mobility.csv`, which are ten verbatim rows of the public Opportunity Insights CSVs.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research.event_factors import agreement  # noqa: E402
from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
META = ("mechanism", "payer", "constraint", "source_culture", "participant_structure",
        "failure_mode_hypothesis", "crowding_prior")


def _parse(sid: str, ctx: A.Ctx | None = None) -> dict[tuple[str, date], A.Obs]:
    src = A.BY_ID[sid]
    assert src.parse is not None
    fp = sorted(FIX.glob(f"{sid}.*"))[0]
    return {(o.series, o.period): o for o in src.parse(fp.read_bytes(), ctx or A.Ctx())}


# ============================================================================ GDELT
def test_gdelt_parses_plain_and_zipped_exports_to_partial_sums() -> None:
    raw = (FIX / "gdelt_events_country.csv").read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("20260929001500.export.CSV", raw)
    for body in (raw, buf.getvalue()):
        got = {o.series: o.value for o in A.parse_gdelt_events(body, A.Ctx())}
        assert got["CN|n"] == 3 and got["CN|art"] == 8
        assert got["CN|tone_art"] == pytest.approx(2.5 * 4 - 4.0 * 2 - 6.0 * 2)
        assert got["CN|conflict_art"] == 4                      # quad 3 and 4 articles
        assert got["CN|theme_protest"] == 1 and got["CN|theme_sanction"] == 1
        assert got["JP|theme_econ_coop"] == 1 and got["KR|theme_violence"] == 1
        assert not any(k.startswith("XX") for k in got)          # unmapped country dropped


def _slots(day: str) -> list[str]:
    return [f"{day}{k // 4:02d}{(k % 4) * 15:02d}00" for k in range(96)]


def test_gdelt_day_publishes_only_when_all_96_slots_are_read() -> None:
    obs = A.parse_gdelt_events((FIX / "gdelt_events_country.csv").read_bytes(), A.Ctx())
    many = [A.Obs(o.series, o.period, o.value * 10) for o in obs]   # 30 CN events per slot 0
    acc: dict[str, Any] = {}
    slots = _slots("20260929")
    A.gdelt_accumulate(acc, slots[0], many)
    A.gdelt_accumulate(acc, slots[0], many)                         # idempotent per slot
    for s in slots[1:95]:
        A.gdelt_accumulate(acc, s, [])
    done, dropped = A.gdelt_complete_days(acc)
    assert done == [] and dropped == [] and "2026-09-29" in acc     # one slot still unread
    A.gdelt_accumulate(acc, slots[95], None)                        # a 404: read, empty
    done, dropped = A.gdelt_complete_days(acc)
    got = {o.series: o.value for o in done}
    assert got["CN_events"] == 30
    assert got["CN_tone"] == pytest.approx((2.5 * 4 - 4.0 * 2 - 6.0 * 2) / 8)
    assert got["CN_conflict_share"] == pytest.approx(0.5)
    assert "JP_tone" not in got                                     # 10 events < minimum
    assert acc == {}


def test_gdelt_day_with_too_many_gaps_is_dropped_not_guessed() -> None:
    acc: dict[str, Any] = {}
    slots = _slots("20260928")
    for i, s in enumerate(slots):
        A.gdelt_accumulate(acc, s, None if i < A.GDELT_MAX_MISSING_SLOTS + 1 else [])
    done, dropped = A.gdelt_complete_days(acc)
    assert done == [] and dropped == ["2026-09-28"]


def test_gdelt_cursor_moves_only_over_read_slots(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    src = A.BY_ID["gdelt_events_country"]
    sst: dict[str, Any] = {}
    calls: list[str] = []

    def getter(url: str) -> tuple[bytes, str]:
        calls.append(url)
        slot = url.rsplit("/", 1)[1][:14]
        if slot.endswith("003000"):
            raise urllib.error.HTTPError(url, 404, "nf", None, None)  # type: ignore[arg-type]
        if slot.endswith("010000"):
            raise urllib.error.HTTPError(url, 500, "err", None, None)  # type: ignore[arg-type]
        return b"", "application/zip"

    rec = A.collect_gdelt(paths, src, sst, {}, NOW, fetch=True, fixtures=None, deadline=1e18,
                          getter=getter)
    # forward: 00:00, 00:15, 00:30 (404 = read), 00:45, then 01:00 fails -> stops there
    assert sst["fwd"] == "2026-09-29T01:00:00+00:00"
    assert rec["errors"] and "20260929010000" in rec["errors"][0]
    assert "20260929003000" in sst["acc"]["2026-09-29"]["missing"]
    # backward direction kept going after the forward error
    assert sst["back"] < "2026-09-28T21:00:00+00:00"
    assert all(c.startswith("http://data.gdeltproject.org/gdeltv2/") for c in calls)


def test_gdelt_fixture_pass_publishes_the_country_panel(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    src = A.BY_ID["gdelt_events_country"]
    store: dict[str, Any] = {}
    rec = A.collect_gdelt(paths, src, {}, store, NOW, fetch=False, fixtures=FIX, deadline=1e18)
    assert rec["days_published"] == [] or rec["days_published"] == ["2026-09-29"]
    # the fixture day has 3 CN events (< GDELT_MIN_EVENTS): nothing is published from it
    assert not any(k.startswith("CN_tone") for k in store)


# ============================================================================ text / JSON parsers
def test_card_spend_parsers() -> None:
    oi = _parse("us_oi_card_spend")
    assert oi[("spend_all", date(2021, 3, 1))].value == pytest.approx(0.0403)
    assert oi[("spend_food_accommodation", date(2021, 3, 1))].value == pytest.approx(-0.0705)
    ecos = _parse("kr_bok_card_spend")
    assert ecos[("card_spend", date(2026, 7, 31))].value == pytest.approx(99876.5)
    assert len(ecos) == 2                                             # "-" is not a value
    meti = _parse("jp_meti_retail")
    assert meti[("retail_yoy", date(2026, 8, 31))].value == pytest.approx(2.8)
    assert meti[("retail_yoy", date(2026, 7, 31))].value == pytest.approx(-0.4)   # ▲
    assert meti[("retail_yoy", date(2026, 8, 31))].published_at == datetime(2026, 9, 29,
                                                                            tzinfo=UTC)
    nbs = _parse("cn_nbs_retail")
    assert nbs[("retail_yoy", date(2026, 8, 31))].value == pytest.approx(3.4)
    assert len(nbs) == 2                                              # 1-8月 cumulative skipped
    assert nbs[("retail_yoy", date(2026, 8, 31))].published_at == datetime(2026, 9, 15, 2,
                                                                           tzinfo=UTC)
    hol = _parse("cn_holiday_spend")
    assert hol[("spend_yoy", date(2026, 10, 8))].value == pytest.approx(6.2)
    assert hol[("spend_per_trip_yoy", date(2026, 10, 8))].value == pytest.approx(
        (1.062 / 1.05 - 1) * 100, abs=1e-3)
    assert hol[("unionpay_amount_yoy", date(2026, 10, 8))].value == pytest.approx(7.5)
    upi = _parse("in_npci_upi")
    assert upi[("upi_value_cr", date(2026, 8, 31))].value == pytest.approx(2610345.67)
    bkm = _parse("tr_bkm_card")
    assert bkm[("card_payments_nominal_yoy", date(2026, 8, 31))].value == pytest.approx(48.5)
    icva = _parse("br_cielo_icva")
    assert icva[("icva_deflated_yoy", date(2026, 8, 31))].value == pytest.approx(1.8)
    assert icva[("icva_nominal_yoy", date(2026, 8, 31))].value == pytest.approx(6.2)
    assert _parse("mx_antad_sss")[("same_store_sales_yoy", date(2026, 8, 31))].value == 3.7
    assert _parse("za_beti")[("beti_mom", date(2026, 8, 31))].value == pytest.approx(1.2)


def test_foot_traffic_parsers() -> None:
    assert _parse("us_oi_google_mobility")[("retail_and_recreation",
                                            date(2021, 3, 1))].value == pytest.approx(-0.166)
    kobis = _parse("kr_kobis_box_office")
    assert kobis[("audience_top10", date(2026, 9, 28))].value == 121300
    seoul = _parse("kr_seoul_subway")
    o = seoul[("boardings", date(2026, 9, 25))]
    assert o.value == 218000 and o.published_at == datetime(2026, 9, 28, 15, tzinfo=UTC)
    mao = _parse("cn_maoyan_box_office")
    assert mao[("box_office_cny_10k", date(2026, 9, 28))].value == pytest.approx(12500)
    bd = _parse("cn_baidu_migration", A.Ctx(part="shanghai"))
    assert bd[("shanghai_move_in", date(2026, 9, 28))].value == pytest.approx(6.02)
    wiki = _parse("wiki_asia_attention", A.Ctx(part="ja_boj"))
    assert wiki[("ja_boj_views", date(2026, 9, 28))].value == 2950


def test_satellite_substitute_parsers() -> None:
    busan = _parse("kr_busan_port")
    assert busan[("container_yoy", date(2026, 8, 31))].value == pytest.approx(3.1)
    assert busan[("container_10k_teu", date(2026, 8, 31))].published_at == datetime(
        2026, 9, 18, tzinfo=UTC)
    sg = _parse("sg_port_throughput")
    assert sg[("container_throughput_k_teu", date(2026, 8, 31))].value == pytest.approx(3612.4)
    assert not any(s == "vessel_arrivals" for s, _ in sg)
    mot = _parse("cn_mot_port_weekly")
    assert mot[("container_wow", date(2026, 9, 21))].value == pytest.approx(-0.6)
    assert mot[("port_cargo_100m_t", date(2026, 9, 21))].published_at == datetime(
        2026, 9, 24, 12, tzinfo=UTC)


def test_partial_or_live_day_rows_are_never_emitted() -> None:
    doc = json.loads((FIX / "kr_seoul_subway.json").read_text("utf-8"))
    doc["CardSubwayStatsNew"]["list_total_count"] = 700               # page holds 3 of 700
    assert A.parse_seoul_subway(json.dumps(doc).encode(), A.Ctx()) == []
    today = A.Ctx(fetched_at=datetime(2026, 9, 28, 20, tzinfo=UTC))
    assert A.parse_maoyan((FIX / "cn_maoyan_box_office.json").read_bytes(), today) == []
    assert A.parse_baidu_migration((FIX / "cn_baidu_migration.txt").read_bytes(),
                                   A.Ctx(part="beijing", fetched_at=today.fetched_at)) != []
    got = A.parse_baidu_migration((FIX / "cn_baidu_migration.txt").read_bytes(),
                                  A.Ctx(part="beijing", fetched_at=today.fetched_at))
    assert max(o.period for o in got) < date(2026, 9, 28)


# ============================================================================ cursors / keys
def test_dated_requests_carry_the_key_only_in_the_live_url_and_backfill_commits_on_success(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "kobis-test-secret-000"
    monkeypatch.setenv("KOBIS_API_KEY", secret)
    src = A.BY_ID["kr_kobis_box_office"]
    assert A.status_of(src) == "UNMEASURED_LIVE_YIELD"
    paths = A.Paths(tmp_path / "desk")
    state: dict[str, Any] = {}
    body = (FIX / "kr_kobis_box_office.json").read_bytes()
    rec = A.collect(paths, src, state, NOW, fetch=True, fixtures=None, deadline=1e18,
                    getter=lambda url: (body, "application/json"))
    assert rec["fetched"] == 21 and not rec["errors"]
    sst = state["sources"][src.id]
    assert sst["backfill_to"] < "2026-09-23" and "backfill_to_next" not in sst
    metas = list((paths.vault / f"alt_{src.id}").glob("*.meta.json"))
    assert metas and all(secret not in m.read_text("utf-8") for m in metas)
    assert "<KOBIS_API_KEY>" in metas[0].read_text("utf-8")
    # a failing pass does not move the backfill cursor
    before = sst["backfill_to"]
    A.collect(paths, src, state, NOW, fetch=True, fixtures=None, deadline=1e18,
              getter=lambda url: (_ for _ in ()).throw(OSError("down")))
    assert state["sources"][src.id]["backfill_to"] == before


def test_keyed_substitutes_block_without_their_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for env in ("ECOS_API_KEY", "KOBIS_API_KEY", "SEOUL_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    got = {s.id: A.status_of(s) for s in A.SUBSTITUTE_SOURCES if s.key_env}
    assert got == {"kr_bok_card_spend": "BLOCKED_ON_KEY:ECOS_API_KEY",
                   "kr_kobis_box_office": "BLOCKED_ON_KEY:KOBIS_API_KEY",
                   "kr_seoul_subway": "BLOCKED_ON_KEY:SEOUL_API_KEY"}
    assert A.status_of(A.BY_ID["us_oi_card_spend"]) == "ARCHIVE_ENDED:2024-06"


def test_wiki_requests_full_history_once_then_a_window() -> None:
    src = A.BY_ID["wiki_asia_attention"]
    st: dict[str, Any] = {}
    first = A.requests_for(src, NOW, st)
    assert len(first) == len(A.WIKI_ASIA_ARTICLES) and "/20150701/" in first[0].url
    assert "%E6%97%A5%E6%9C%AC%E9%8A%80%E8%A1%8C" in first[0].url         # 日本銀行, quoted
    later = A.requests_for(src, NOW, {"full_done": True})
    assert "/20260816/" in later[0].url


# ============================================================================ transforms
def test_yoy_monthly_uses_the_same_month_a_year_earlier_only() -> None:
    src = A.BY_ID["in_npci_upi"]
    obs = [A.Obs("upi_value_cr", A._month_end(2024 + (m - 1) // 12, (m - 1) % 12 + 1),
                 100.0 + m) for m in range(1, 27)]
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, obs, NOW)
    pts = A.build_points(src, store)["upi_value_cr"]
    by = {p["d"]: p["pace"] for p in pts}
    assert by["2024-12-31"] is None
    assert by["2025-03-31"] == pytest.approx((115.0 / 103.0 - 1) * 100, abs=1e-4)


def test_every_substitute_rule_is_after_its_period() -> None:
    for s in A.SUBSTITUTE_SOURCES:
        for d in (date(2026, 1, 31), date(2026, 9, 20)):
            assert s.rule(d) > datetime(d.year, d.month, d.day, tzinfo=UTC), s.id


# ============================================================================ agreement
def test_agreement_is_unmeasured_on_few_points_and_exact_on_identity() -> None:
    few = {i: float(i) for i in range(5)}
    assert agreement(few, few)["verdict"] == "UNMEASURED"
    xs = {i: float(i % 7) + i * 0.01 for i in range(40)}
    got = agreement(xs, xs)
    assert got["pearson"] == pytest.approx(1.0) and got["spearman"] == pytest.approx(1.0)
    assert agreement(xs, {k: -v for k, v in xs.items()})["pearson"] == pytest.approx(-1.0)


def _pts(values: dict[date, float]) -> list[dict[str, Any]]:
    return [{"d": d.isoformat(), "value": v} for d, v in sorted(values.items())]


def test_substitute_agreement_measures_overlaps_and_names_what_is_missing(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    days = [date(2021, 1, 1) + timedelta(days=i) for i in range(120)]
    spend = {d: (i % 11) * 0.01 for i, d in enumerate(days)}
    visits = {d: v * 2 + 0.001 * (i % 3) for i, (d, v) in enumerate(spend.items())}
    pts = {"us_oi_card_spend": {"spend_retail_no_grocery": _pts(spend),
                                "spend_all": _pts(spend)},
           "us_oi_google_mobility": {"retail_and_recreation": _pts(visits)},
           "gdelt_events_country": {"CN_conflict_share": _pts(spend),
                                     "CN_tone": _pts({d: -v for d, v in spend.items()})}}
    paths.series.mkdir(parents=True)
    pd.DataFrame({"period": [d.isoformat() for d in days],
                  "available_time": [(d + timedelta(days=1)).isoformat() for d in days],
                  "geopolitical_risk_intensity": [spend[d] for d in days]}).to_parquet(
        paths.series / "nlp_events_CN.parquet", index=False)
    got = A.substitute_agreement(paths, pts)
    assert got["oi_card_vs_google_mobility_level"]["verdict"] == "MEASURED"
    assert got["oi_card_vs_google_mobility_level"]["pearson"] > 0.99
    assert got["oi_card_vs_census_marts_mom"]["verdict"] == "UNMEASURED"
    g = got["gdelt_conflict_share_vs_tagger_geopolitical_risk"]
    assert g["verdict"] == "MEASURED" and g["n"] == 120 and g["pearson"] == pytest.approx(1.0)
    assert got["gdelt_negative_tone_vs_tagger_geopolitical_risk"]["pearson"] == pytest.approx(1.0)
    assert got["vs_paid_original"]["verdict"] == "UNMEASURED"


# ============================================================================ roster
def test_substitute_roster_rows_carry_the_culture_fields_and_ownership() -> None:
    rows = A.substitute_roster_rows()
    assert len(rows) == len(A.SUBSTITUTE_SOURCES) >= 18
    for r in rows:
        for k in (*META, "substitutes_for", "cursor", "pit", "licence", "status"):
            assert r.get(k), (r["id"], k)
        assert r["fetcher"] == "owned" and r["owner"] == "asia_gap_thread"
        assert r["consumer"] == "desks/mt5/research/alt_proxies.py"
        assert "{key}" not in r["url"]


def test_repo_roster_file_matches_the_code_and_parses() -> None:
    fp = DESK / "data" / "source_rosters" / "asia_paid_substitutes_consumer.yaml"
    doc = yaml.safe_load(fp.read_text("utf-8"))
    ids = [r["id"] for r in doc["sources"]]
    assert len(ids) == len(set(ids))
    assert set(ids) == {s.id for s in A.SUBSTITUTE_SOURCES}
    for r in doc["sources"]:
        assert r["fetcher"] == "owned" and r["owner"] == "asia_gap_thread"
        assert r["auth"] in ("none", "key") and (r["auth"] == "none" or r["auth_env"])
        for k in (*META, "substitutes_for", "consumer", "uses", "cadence_minutes"):
            assert r.get(k), (r["id"], k)
