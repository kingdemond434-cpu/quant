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
    for env in ("ECOS_API_KEY", "KOBIS_API_KEY", "SEOUL_API_KEY", "ESTAT_APP_ID", "INEGI_TOKEN",
                "DATA_GO_KR_KEY"):
        monkeypatch.delenv(env, raising=False)
    got = {s.id: A.status_of(s) for s in A.SUBSTITUTE_SOURCES if s.key_env}
    assert got == {"kr_bok_card_spend": "BLOCKED_ON_KEY:ECOS_API_KEY",
                   "kr_kobis_box_office": "BLOCKED_ON_KEY:KOBIS_API_KEY",
                   "kr_seoul_subway": "BLOCKED_ON_KEY:SEOUL_API_KEY",
                   "jp_estat_immigration": "BLOCKED_ON_KEY:ESTAT_APP_ID",
                   "mx_inegi_emec": "BLOCKED_ON_KEY:INEGI_TOKEN",
                   "kr_mof_container_teu": "BLOCKED_ON_KEY:DATA_GO_KR_KEY"}
    assert A.status_of(A.BY_ID["us_oi_card_spend"]) == "DEAD:2024-06"
    assert A.status_of(A.BY_ID["us_oi_google_mobility"]) == "DEAD:2022-10"


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


def test_substitute_agreement_is_on_changes_split_by_regime(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    days = [date(2020, 3, 1) + timedelta(days=i) for i in range(1400)]
    spend = {d: float((i * 37) % 101) * 0.01 for i, d in enumerate(days)}
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
    m = got["oi_card_vs_google_mobility"]
    assert m["basis"] == "changes"
    assert set(m["changes"]) == {"all", "pre_2021", "2021_plus"}
    n_weeks = m["changes"]["all"]["n"]
    assert n_weeks == len([d for d in days if d.weekday() == 6]) - 1     # non-overlapping
    assert m["changes"]["pre_2021"]["n"] + m["changes"]["2021_plus"]["n"] == n_weeks
    assert m["changes"]["2021_plus"]["pearson"] > 0.99
    assert "levels_context_only" in m                                 # never levels alone
    assert got["oi_card_vs_census_marts_mom"]["verdict"] == "UNMEASURED"
    g = got["gdelt_conflict_share_vs_tagger_geopolitical_risk"]
    assert g["changes"]["all"]["verdict"] == "MEASURED"
    assert g["changes"]["all"]["pearson"] == pytest.approx(1.0)
    assert got["gdelt_negative_tone_vs_tagger_geopolitical_risk"]["changes"]["all"][
        "pearson"] == pytest.approx(1.0)
    po = got["paid_original_agreement"]
    assert set(po) == {"news_analytics", "card_panels", "foot_traffic", "satellite"}
    for row in po.values():                    # no number without fetched data behind it
        assert row["verdict"] == "UNMEASURED" and row["why"] and row["paid_original"]
        assert set(row["substitutes"]) <= set(A.BY_ID)


def test_weekly_change_is_non_overlapping() -> None:
    days = {date(2024, 1, 1) + timedelta(days=i): float(i) for i in range(30)}
    wk = A._weekly_change(days)
    assert wk and all(d.weekday() == 6 and v == 7.0 for d, v in wk.items())
    keyed = A._weekly_change({(d, "CN"): v for d, v in days.items()})
    assert set(keyed) == {(d, "CN") for d in wk}


# ============================================================================ terms / status
def test_every_source_has_an_explicit_terms_entry() -> None:
    assert set(A.TERMS) == set(A.BY_ID)
    for s in A.SOURCES:
        assert s.terms in A.TERMS_VALUES and s.terms == A.TERMS[s.id][0], s.id
    for sid in ("cn_maoyan_box_office", "cn_baidu_migration"):
        assert A.BY_ID[sid].terms != "confirmed"
    assert A.BY_ID["cn_maoyan_box_office"].terms == "refused"


def test_reviewed_terms_carry_evidence() -> None:
    assert set(A.TERMS_EVIDENCE) <= set(A.TERMS)
    for sid, ev in A.TERMS_EVIDENCE.items():
        assert ev["terms_url"].startswith("https://") and ev["terms_quote"], sid
        # 2026-09-30 is the original review; 2026-10-06 the re-read of SGE's terms (refused).
        assert ev["robots"] and ev["checked_at"] in ("2026-09-30", "2026-10-06"), sid
    reviewed = {sid for sid in A.TERMS_EVIDENCE if A.TERMS[sid][0] == "confirmed"}
    assert reviewed == {"cn_nbs_retail", *NEW_SUBSTITUTES}


def test_sge_terms_are_refused_and_the_gate_governs_the_whole_host() -> None:
    assert A.TERMS["cn_sge_premium"][0] == "refused"
    assert "no institution or individual may disseminate" in (
        A.TERMS_EVIDENCE["cn_sge_premium"]["terms_quote"])
    for url in ("https://www.sge.com.cn/graph/quotations", "https://en.sge.com.cn/data_Licensed",
                "https://www.sge.com.cn/sjzx/mrhq"):
        assert A.terms_gate(url)[0] == "refused", url
    assert A.terms_gate("https://www.safe.gov.cn/safe/whxsdsj/index.html")[0] == "ungoverned"
    assert A.terms_gate("no_such_row")[0] == "to_confirm"            # fail closed


def test_a_to_confirm_source_is_never_fetched(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")

    def boom(url: str) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")

    for src in A.SOURCES:
        if src.terms == "confirmed":
            continue
        assert A.status_of(src).startswith(("BLOCKED_ON_TERMS:", "BLOCKED+SUBSTITUTE:",
                                            "DEAD:")), src.id
        for fixtures in (None, FIX):
            rec = A.collect(paths, src, {}, NOW, fetch=True, fixtures=fixtures,
                            deadline=1e18, getter=boom)
            assert rec["status"] == A.status_of(src) and rec["requests"] == 0
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    for sid in ("cn_maoyan_box_office", "cn_baidu_migration"):
        assert rep["sources"][sid]["series"] == {}
        assert sid in rep["blocked_on_terms"]


def test_ecos_never_builds_a_request_on_a_placeholder_code(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = A.BY_ID["kr_bok_card_spend"]
    for env in ("ALT_ECOS_CARD_STAT", "ALT_ECOS_CARD_ITEM"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.delenv("ECOS_API_KEY", raising=False)
    assert A.status_of(src) == "BLOCKED_ON_KEY:ECOS_API_KEY"
    monkeypatch.setenv("ECOS_API_KEY", "k")
    assert A.status_of(src) == "UNCONFIGURED:ALT_ECOS_CARD_STAT,ALT_ECOS_CARD_ITEM"
    assert A.requests_for(src, NOW, {}) == []
    rec = A.collect(A.Paths(tmp_path / "desk"), src, {}, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=lambda u: (_ for _ in ()).throw(AssertionError(u)))
    assert rec["status"].startswith("UNCONFIGURED")
    monkeypatch.setenv("ALT_ECOS_CARD_STAT", "901Y999")
    assert A.requests_for(src, NOW, {}) == []                        # one code is not both
    monkeypatch.setenv("ALT_ECOS_CARD_ITEM", "I61A")
    assert A.status_of(src) == "UNMEASURED_LIVE_YIELD"
    (req,) = A.requests_for(src, NOW, {})
    assert req.url.endswith("/901Y999/M/201801/202609/I61A") and "{" not in req.url


def test_no_source_claims_live_yield_and_dead_archives_never_count_as_live() -> None:
    for s in A.SOURCES:
        assert "LIVE" not in A.status_of(s).replace("UNMEASURED_LIVE_YIELD", ""), s.id
    rep = {"at": NOW.isoformat(), "mode": "fetch",
           "sources": {"us_oi_card_spend": {"status": "DEAD:2024-06", "parsed": 900,
                                            "series": {"spend_all": 900}}}}
    assert A.digest_section(rep)["status"] == "UNMEASURED_LIVE_YIELD"


# ============================================================================ lane
def test_no_direct_cell_has_a_share_cfd_symbol(tmp_path: Path) -> None:
    from research import universe_policy
    gains: dict[str, dict[str, Any]] = {}
    for s in A.SOURCES:
        for series in s.signal_series:
            for sym in s.instruments_for(series):
                gains[f"{s.id}|{series}|{sym}"] = {"verdict": "PASS", "ic": 0.2, "n": 50}
    assert any(universe_policy.is_equity(k.split("|")[2]) for k in gains)   # they are mapped
    cells = A.direct_cells(gains, NOW)
    assert cells and not any(universe_policy.is_equity(c["symbol"]) for c in cells)
    assert all(not A.BY_ID[c["provenance"]["source_id"]].archive_until for c in cells)
    # the gain tests never spend a trial on one either
    src = A.BY_ID["kr_exports_early"]
    pts = {"semis_yoy": [{"available_time": "2026-01-10T00:00:00+00:00", "surprise_z": 1.0,
                          "pit_quality": "live", "d": "2026-01-09", "value": 1.0}]}
    keys = A.gain_tests(A.Paths(tmp_path / "desk"), {src.id: pts})
    assert keys and not any(universe_policy.is_equity(k.split("|")[2]) for k in keys)
    assert "kr_exports_early|semis_yoy|USDKRW" in keys


def test_share_cfd_series_go_to_the_equity_handoff() -> None:
    from research import universe_policy
    doc = A.equity_handoff()
    rows = {(r["source"], r["series"]): r for r in doc["rows"]}
    semis = rows[("kr_exports_early", "semis_yoy")]
    assert semis["shares"]["TSMC"] == 1 and "USDKRW" not in semis["shares"]
    for r in doc["rows"]:
        assert r["shares"] and all(universe_policy.is_equity(s) for s in r["shares"])
        assert all(v in (1, -1) for v in r["shares"].values())
    committed = json.loads((DESK / "data" / "digests" / "alt_proxies_equity_handoff.json"
                            ).read_text("utf-8"))
    assert committed["rows"] == doc["rows"]


# ============================================================================ trials
def test_a_null_pass_is_charged_to_the_lifetime_ledger_once(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import experiment_ledger as L
    from research import proposer_common as pc
    paths = A.Paths(tmp_path / "desk")
    monkeypatch.setattr(L, "DESK", paths.desk)
    base, _ = L._proposer_counts()
    res = A._donate(paths, A.SOURCE, [], 7, {"exogenous_conditioner": 7}, NOW)
    assert res["null_trials_charged"] == 7
    total, fam = L._proposer_counts()
    assert total == base + 7 and fam["exogenous_conditioner"] == 7
    # a pass whose discovery file carries tests_run is NOT also written to the side ledger
    monkeypatch.setattr(pc, "donate", lambda *a, **k: tmp_path / "discoveries_x.json")
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": 1})
    res = A._donate(paths, A.SOURCE, [{"cell": "x"}], 9, {"exogenous_conditioner": 9}, NOW)
    assert "null_trials_charged" not in res
    assert L._proposer_counts()[0] == base + 7
    # nothing tested, nothing charged
    assert "null_trials_charged" not in A._donate(paths, A.SOURCE, [], 0, {}, NOW)


# ============================================================================ power
def test_placebo_gates_hold_the_null_false_positive_rate_at_or_below_alpha() -> None:
    """The null row of the power table is the false-positive rate. It must not sit above alpha
    by more than its own sampling error (one-sided binomial, 1.96 SE, fixed seeds)."""
    import math

    from libs.research.release_gain import ALPHA_FAMILY, power_table
    rows = power_table(ics=(0.0,), ns=(250,), n_sims=30, gates=("release_gain",))
    rows += power_table(ics=(0.0,), ns=(250, 1000), n_sims=400, gates=("regime_placebo",),
                        regime_masks=1000)
    for r in rows:
        se = math.sqrt(ALPHA_FAMILY * (1 - ALPHA_FAMILY) / r["n_sims"])
        assert r["pass_rate"] <= ALPHA_FAMILY + 1.96 * se, r


def test_power_is_reported_and_a_low_power_miss_is_underpowered_not_fail() -> None:
    from libs.research.release_gain import TARGET_IC, min_detectable_ic, power_table
    rows = power_table(ics=(0.05, 0.5), ns=(250,), n_sims=10)
    by = {(r["gate"], r["planted_ic"]): r for r in rows}
    for gate in ("release_gain", "regime_placebo"):
        assert 0.0 <= by[(gate, 0.05)]["pass_rate"] <= 1.0
        assert by[(gate, 0.05)]["min_detectable_ic"] > TARGET_IC      # n=250 cannot see 0.05
        assert by[(gate, 0.5)]["pass_rate"] >= 0.8                     # a large IC is seen
        print(gate, by[(gate, 0.05)])
    assert by[("release_gain", 0.05)]["underpowered_rate"] > 0
    m250, m1000 = min_detectable_ic(250), min_detectable_ic(1000)
    assert m250 is not None and m1000 is not None and m1000 < m250
    assert (min_detectable_ic(1000, 40) or 0.0) > m1000             # the charge costs power


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
    # every row's terms and status are the code's, not just its id (status as declared, no keys)
    code = {r["id"]: r for r in A.roster_file_rows()}
    for r in doc["sources"]:
        c = A.BY_ID[r["id"]]
        assert r["terms"] == c.terms == A.TERMS[c.id][0], r["id"]
        assert r["status"] == A.status_of(c, {}) == code[r["id"]]["status"], r["id"]
        assert r.get("substituted_by") == code[r["id"]].get("substituted_by"), r["id"]
    assert doc["sources"] == A.roster_file_rows()           # regenerated, never hand-edited
    for r in doc["sources"]:
        assert r["fetcher"] == "owned" and r["owner"] == "asia_gap_thread"
        assert r["auth"] in ("none", "key") and (r["auth"] == "none" or r["auth_env"])
        for k in (*META, "substitutes_for", "consumer", "uses", "cadence_minutes"):
            assert r.get(k), (r["id"], k)


# ============================================================================ blocked -> substitute
NEW_SUBSTITUTES = ("jp_estat_immigration", "hk_immd_passenger", "br_bcb_payments",
                   "mx_inegi_emec", "tr_tuik_retail", "kr_mof_container_teu")
BLOCKED = ("jp_jnto_arrivals", "cn_holiday_spend", "tr_bkm_card", "br_cielo_icva", "mx_antad_sss",
           "cn_maoyan_box_office", "in_npci_upi", "cn_sge_premium", "cn_baidu_migration",
           "za_beti", "kr_busan_port", "cn_mot_port_weekly")


def test_every_blocked_source_is_substituted_or_says_why_not() -> None:
    blocked = {s.id for s in A.SOURCES if s.terms != "confirmed"}
    assert blocked == set(BLOCKED)
    assert set(A.SUBSTITUTED_BY) | set(A.NO_SUBSTITUTE) == blocked
    assert not set(A.SUBSTITUTED_BY) & set(A.NO_SUBSTITUTE)
    for sid, subs in A.SUBSTITUTED_BY.items():
        assert subs and len(subs) == len(set(subs)), sid
        for x in subs:
            sub = A.BY_ID[x]
            assert sub.terms == "confirmed" and not sub.archive_until, (sid, x)
            assert x not in A.SUBSTITUTED_BY, x                     # never a blocked stand-in
        assert A.status_of(A.BY_ID[sid]) == "BLOCKED+SUBSTITUTE:" + ",".join(subs)
    for sid, why in A.NO_SUBSTITUTE.items():
        assert why and A.status_of(A.BY_ID[sid]) == f"BLOCKED_ON_TERMS:{A.BY_ID[sid].terms}"


def test_a_substituted_source_is_still_never_fetched(tmp_path: Path) -> None:
    def boom(url: str) -> tuple[bytes, str]:
        raise AssertionError(f"fetched {url}")

    paths = A.Paths(tmp_path / "desk")
    rec = A.collect(paths, A.BY_ID["tr_bkm_card"], {}, NOW, fetch=True, fixtures=None,
                    deadline=1e18, getter=boom)
    assert rec == {**rec, "status": "BLOCKED+SUBSTITUTE:tr_tuik_retail", "requests": 0}
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    assert rep["blocked_substituted"]["kr_busan_port"] == ["kr_mof_container_teu",
                                                           "imf_portwatch_ports"]
    assert set(rep["blocked_unsubstituted"]) == {"in_npci_upi", "za_beti"}
    assert rep["sources"]["tr_bkm_card"]["status"].startswith("BLOCKED+SUBSTITUTE:")
    rows = {r["id"]: r for r in A.roster_rows()}
    assert rows["jp_jnto_arrivals"]["substituted_by"] == ["jp_estat_immigration"]
    assert "substituted_by" not in rows["in_npci_upi"]


def test_new_substitute_rows_carry_schema_terms_and_evidence() -> None:
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for sid in NEW_SUBSTITUTES:
        s = A.BY_ID[sid]
        assert s in A.SUBSTITUTE_SOURCES and s.substitutes_for, sid
        assert s.terms == A.TERMS[sid][0] == "confirmed", sid
        ev = A.TERMS_EVIDENCE[sid]
        assert ev["terms_url"].startswith("https://") and ev["terms_quote"].strip("( "), sid
        assert not ev["terms_quote"].startswith("(not"), sid     # a verbatim quote, not a gap
        for k in META:
            assert getattr(s, k), (sid, k)
        assert s.crowding_prior in ("low", "medium", "high")
        assert s.parse is not None and s.signal_series and s.transform
        for m in (s.instruments, *s.series_instruments.values()):
            assert m and set(m) <= set(uni) and set(m.values()) <= {1, -1}, sid
            assert all(A.may_mint(sym) for sym in m), sid          # index/FX only: never a share
        for d in (date(2026, 1, 31), date(2026, 8, 31)):
            assert s.rule(d) > datetime(d.year, d.month, d.day, tzinfo=UTC), sid
        assert "{key}" not in A.roster_rows([s])[0]["url"]


def test_new_substitute_parsers_read_their_fixtures() -> None:
    ctx = A.Ctx(fetched_at=NOW)
    im = _parse("jp_estat_immigration")
    assert im[("foreign_entries", date(2026, 8, 31))].value == 3420000      # the total, not a sum
    hk = _parse("hk_immd_passenger", ctx)
    assert hk[("mainland_visitor_arrivals", date(2026, 9, 28))].value == 30000
    assert hk[("hk_resident_departures", date(2026, 9, 28))].value == 24000
    same_day = A.Ctx(fetched_at=datetime(2026, 9, 28, 20, tzinfo=UTC))    # today never emitted
    got = A.parse_hk_immd((FIX / "hk_immd_passenger.csv").read_bytes(), same_day)
    assert got and all(o.period < date(2026, 9, 28) for o in got)
    br = _parse("br_bcb_payments")
    assert br[("retail_payments_value_brl", date(2026, 8, 31))].value == pytest.approx(4190000.0)
    mx = _parse("mx_inegi_emec")
    assert mx[("retail_index", date(2026, 6, 30))].value == pytest.approx(118.4)
    tr = _parse("tr_tuik_retail")
    o = tr[("retail_volume_yoy", date(2026, 7, 31))]
    assert o.value == pytest.approx(12.7) and o.published_at == datetime(2026, 9, 4, 10,
                                                                          tzinfo=UTC)
    kr = _parse("kr_mof_container_teu")
    assert kr[("container_teu", date(2026, 8, 31))].value == 1150000 + 1170000 + 92000 + 97000
    doc = json.loads((FIX / "kr_mof_container_teu.json").read_text("utf-8"))
    doc["response"]["body"]["totalCount"] = 40                          # page holds 4 of 40
    assert A.parse_kr_mof_container(json.dumps(doc).encode(), ctx) == []
    xml = (b"<response><body><items><item><useYm>202608</useYm><eContnTeuTotal>10"
           b"</eContnTeuTotal><tContnTeuTotal>5</tContnTeuTotal></item></items>"
           b"<totalCount>1</totalCount></body></response>")
    assert A.parse_kr_mof_container(xml, ctx)[0].value == 15


def test_configured_substitutes_never_request_on_a_placeholder(
        monkeypatch: pytest.MonkeyPatch) -> None:
    for env in ("ALT_ESTAT_IMMIG_STATS_ID", "ALT_ESTAT_IMMIG_CAT01", "ALT_INEGI_EMEC_ID",
                "ALT_TUIK_RETAIL_URL"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("ESTAT_APP_ID", "k")
    monkeypatch.setenv("INEGI_TOKEN", "k")
    for sid in ("jp_estat_immigration", "mx_inegi_emec", "tr_tuik_retail"):
        src = A.BY_ID[sid]
        assert A.status_of(src).startswith("UNCONFIGURED:"), sid
        assert A.requests_for(src, NOW, {}) == [], sid


def test_nbs_terms_were_rejudged_against_the_listed_exclusions() -> None:
    ev = A.TERMS_EVIDENCE["cn_nbs_retail"]
    for item in ("a.本网所指向", "b.已作出不得转载", "c.未由本网署名", "d.本网中特有",
                 "e.本网中必须具有特别授权", "f.其他法律不允许"):
        assert item in ev["terms_quote"], item
    assert "Stays confirmed" in ev["judgement"] and A.BY_ID["cn_nbs_retail"].terms == "confirmed"


def test_dead_board_urls_were_replaced() -> None:
    assert "Board.do?mCode=MN1003" not in A.BY_ID["kr_busan_port"].url
    assert "/tongjishuju/" not in A.BY_ID["cn_mot_port_weekly"].url


def test_engine_rows_file_matches_the_code_and_the_engine_can_read_it() -> None:
    fp = DESK / "data" / "paid_data_substitutes_asia_blocked.json"
    doc = json.loads(fp.read_text("utf-8"))
    assert doc == json.loads(json.dumps(A.engine_rows(), ensure_ascii=False))
    rows = {r["paid"].rsplit("[", 1)[1].rstrip("]"): r for r in doc["rows"]}
    assert set(rows) == set(BLOCKED)
    for sid, r in rows.items():
        assert r["status"] == A.status_of(A.BY_ID[sid], {}), sid
        assert list(r)[:3] == ["class", "paid", "free"]      # the engine finds columns by word
        assert bool(r["free"]) == (sid in A.SUBSTITUTED_BY), sid
    lib = {r["id"] for r in doc["library_rows"]}
    assert lib == {f"asia_{x}" for v in A.SUBSTITUTED_BY.values() for x in v}
