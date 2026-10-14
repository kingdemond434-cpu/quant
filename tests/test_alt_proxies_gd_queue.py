"""GD queue rows (2026-10-14) built through alt_proxies: the US net-liquidity weekly regime state
(H.4.1 - TGA - ON RRP) and the HELD routes (CME margin advisories, China credit graph, Cboe
delayed index values). Fixtures are SYNTHETIC pages shaped like each publisher's; no network.
"""
from __future__ import annotations

import json
import sys
import urllib.error
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2024, 10, 7, 12, tzinfo=UTC)
SRC = A.BY_ID[A.NET_LIQ_ID]


def _fx(i: int) -> bytes:
    return sorted(FIX.glob(f"{A.NET_LIQ_ID}.{i}.*"))[0].read_bytes()


def _h41(wed: date, total_m: int) -> bytes:
    """The fixture's H.4.1 page re-dated to another week, with another total."""
    rel = wed + timedelta(days=1)
    page = _fx(2).decode()
    page = page.replace("October 03, 2024", rel.strftime("%B %d, %Y"))
    page = page.replace("Wednesday Oct 2, 2024", f"Wednesday {wed.strftime('%b')} {wed.day}, "
                                                f"{wed.year}")
    return page.replace("7,046,925", f"{total_m:,}", 1).encode()


# ---------------------------------------------------------------------------- parsing + PIT
def test_each_publisher_body_parses_to_its_own_component_in_usd_bn() -> None:
    tga = {o.period: o for o in A.parse_net_liquidity(_fx(0), A.Ctx())}
    rrp = {o.period: o for o in A.parse_net_liquidity(_fx(1), A.Ctx())}
    (walcl,) = A.parse_net_liquidity(_fx(2), A.Ctx())
    wed = date(2024, 10, 2)
    assert {o.series for o in tga.values()} == {"tga_bn"}
    assert tga[wed].value == pytest.approx(823.412)                    # closing row only
    assert tga[date(2021, 9, 29)].value == pytest.approx(173.451)      # pre-2021 account name
    assert rrp[wed].value == pytest.approx(383.398)                    # the repo op is excluded
    assert walcl.series == "walcl_bn" and walcl.period == wed
    assert walcl.value == pytest.approx(7046.925)                      # table 5, not table 6
    # every stamp is AFTER the period and late-biased: H.4.1 Thu 21:30 UTC, DTS next weekday
    # 22:00 UTC, RRP same day 19:00 UTC
    assert walcl.published_at == datetime(2024, 10, 3, 21, 30, tzinfo=UTC)
    assert tga[wed].published_at == datetime(2024, 10, 3, 22, tzinfo=UTC)
    assert rrp[wed].published_at == datetime(2024, 10, 2, 19, tzinfo=UTC)


def test_a_friday_tga_record_is_stamped_on_monday() -> None:
    body = json.dumps({"data": [{"record_date": "2024-10-04", "account_type":
                                 "Treasury General Account (TGA) Closing Balance",
                                 "close_today_bal": "null", "open_today_bal": "800000"}]})
    (o,) = A.parse_net_liquidity(body.encode(), A.Ctx())
    assert o.published_at == datetime(2024, 10, 7, 22, tzinfo=UTC)



def test_a_tga_record_before_a_federal_holiday_rolls_past_it() -> None:
    """GD queue-rows audit MF1: the DTS for Wednesday 2024-11-27 was published Friday 11-29, not
    on Thanksgiving; the component series must never reach the lake a day early."""
    body = json.dumps({"data": [{"record_date": "2024-11-27", "account_type":
                                 "Treasury General Account (TGA) Closing Balance",
                                 "close_today_bal": "null", "open_today_bal": "800000"}]})
    (o,) = A.parse_net_liquidity(body.encode(), A.Ctx())
    assert o.published_at == datetime(2024, 11, 29, 22, tzinfo=UTC)
    assert A.rule_net_liquidity(date(2024, 11, 27)) == datetime(2024, 11, 29, 22, tzinfo=UTC)
    hol = A.us_federal_holidays(2024)
    assert {date(2024, 11, 28), date(2024, 7, 4), date(2024, 6, 19), date(2024, 10, 14),
            date(2024, 11, 11), date(2024, 12, 25), date(2024, 1, 15)} <= hol
    assert date(2026, 7, 3) in A.us_federal_holidays(2026)          # July 4 on a Saturday
    assert date(2021, 12, 31) in A.us_federal_holidays(2021)        # 2022-01-01 is a Saturday

def test_garbage_and_foreign_shapes_parse_to_nothing() -> None:
    for body in (b"<html>maintenance</html>", b"{}", b'{"data": "x"}', b"[1,2]",
                 b"Release Date: October 03, 2024 but no table"):
        assert A.parse_net_liquidity(body, A.Ctx()) == []


def test_the_release_rule_is_late_and_lands_on_a_weekday() -> None:
    for d in (date(2024, 10, 2), date(2024, 10, 4), date(2024, 10, 5)):
        t = A.rule_net_liquidity(d)
        assert t > datetime(d.year, d.month, d.day, 21, 30, tzinfo=UTC) and t.weekday() < 5


# ---------------------------------------------------------------------------- requests
def test_requests_cover_three_publishers_and_walk_h41_back_resumably() -> None:
    st: dict = {}
    reqs = A.requests_for(SRC, NOW, st)
    hosts = {r.url.split("/")[2] for r in reqs}
    assert hosts == {"api.fiscaldata.treasury.gov", "markets.newyorkfed.org",
                     "www.federalreserve.gov"}
    tga = reqs[0].url
    assert f"record_date:gte:{(NOW - timedelta(days=A.NET_LIQ_DEPTH_D)).date()}" in tga
    back = [r for r in reqs if ":back:" in r.ctx.part]
    assert len(back) == A.NET_LIQ_BACK_PER_PASS
    assert all(date.fromisoformat(r.ctx.part.rsplit(":", 1)[1]).weekday() == 3 for r in back)
    assert st["full_done_next"] is True and "backfill_to_next" in st
    later = {"full_done": True, "backfill_to": st["backfill_to_next"]}
    reqs2 = A.requests_for(SRC, NOW, later)
    assert f"gte:{(NOW - timedelta(days=A.NET_LIQ_RECENT_D)).date()}" in reqs2[0].url
    first_back = min(date.fromisoformat(r.ctx.part.rsplit(":", 1)[1]) for r in back)
    assert all(date.fromisoformat(r.ctx.part.rsplit(":", 1)[1]) < first_back
               for r in reqs2 if ":back:" in r.ctx.part)
    deep = {"full_done": True, "backfill_to": (NOW - timedelta(days=A.NET_LIQ_DEPTH_D + 1))
            .date().isoformat()}
    assert not [r for r in A.requests_for(SRC, NOW, deep) if ":back:" in r.ctx.part]


# ---------------------------------------------------------------------------- end to end
def _getter(weeks: list[date]):
    totals = {w: 7000_000 + 9_000 * i for i, w in enumerate(weeks)}

    def get(url: str) -> tuple[bytes, str]:
        if "fiscaldata" in url:
            rows = [{"record_date": w.isoformat(), "account_type":
                     "Treasury General Account (TGA) Closing Balance",
                     "close_today_bal": "null", "open_today_bal": str(800_000 + 2_000 * i)}
                    for i, w in enumerate(weeks)]
            return json.dumps({"data": rows}).encode(), "application/json"
        if "newyorkfed" in url:
            ops = [{"operationDate": w.isoformat(), "operationType": "Reverse Repo",
                    "totalAmtAccepted": 400_000_000_000 - 3_000_000_000 * i}
                   for i, w in enumerate(weeks)]
            return json.dumps({"repo": {"operations": ops}}).encode(), "application/json"
        if url.endswith("/current/"):
            return _h41(weeks[-1], totals[weeks[-1]]), "text/html"
        thu = datetime.strptime(url.rstrip("/").rsplit("/", 1)[1], "%Y%m%d").date()
        wed = thu - timedelta(days=1)
        if wed not in totals or wed == weeks[3]:      # a holiday-shifted week: no page there
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)  # type: ignore[arg-type]
        return _h41(wed, totals[wed]), "text/html"
    return get, totals


def test_net_liquidity_combines_on_wednesdays_at_the_latest_stamp(tmp_path: Path) -> None:
    weeks = [date(2024, 7, 3) + timedelta(days=7 * i) for i in range(14)]
    get, totals = _getter(weeks)
    now = datetime(2024, 10, 7, 12, tzinfo=UTC)
    paths = A.Paths(tmp_path / "desk")
    state: dict = {}
    rec = A.collect(paths, SRC, state, now, fetch=True, fixtures=None, deadline=1e18,
                    getter=get)
    assert rec["status"] == "UNMEASURED_LIVE_YIELD" and not rec["errors"]
    assert any(p.endswith((weeks[3] + timedelta(days=1)).isoformat())
               for p in rec["not_published"])                     # recorded, not an error
    assert "backfill_to" in state["sources"][SRC.id]             # the cursor still moved
    store = json.loads((paths.obs_dir / f"{SRC.id}.json").read_text("utf-8"))
    pts = A.build_points(SRC, store)
    nl = {p["d"]: p for p in pts["net_liquidity"]}
    w = weeks[5]
    p = nl[w.isoformat()]
    want = totals[w] / 1e3 - (800 + 2 * 5) - (400 - 3 * 5)
    assert p["value"] == pytest.approx(want)
    # available only once all three were: the Wednesday TGA's next-weekday 22:00 stamp is later
    # than the H.4.1's Thursday 21:30 and the RRP's Wednesday 19:00, so it governs
    assert p["available_time"] == f"{(w + timedelta(days=1)).isoformat()}T22:00:00+00:00"
    assert weeks[3].isoformat() not in nl                         # missing component, no point
    # pace is the WEEKLY change, and a gap is never a two-week change called weekly
    assert nl[weeks[5].isoformat()]["pace"] == pytest.approx(9 - 2 + 3)
    assert nl[weeks[4].isoformat()]["pace"] is None
    # the axis door and the lake carry it under the organ's own names
    doc = A.axis_doc(SRC, pts, now)
    assert "net_liquidity.pace" in doc["series"] and doc["credit"].startswith("Sources: Board")
    written = A.write_lake_series(paths, SRC, pts)
    assert f"{A.lake_file(SRC, 'net_liquidity')}.csv" in written


def test_the_regime_conditioner_names_the_lake_file() -> None:
    spec = A.conditioner_spec(SRC, "net_liquidity", "pace", "gt", 0.0)
    assert spec == f"alt:{A.lake_file(SRC, 'net_liquidity')}:pace:gt:0"
    assert set(SRC.instruments) >= {"US500", "NAS100", "XAUUSD", "EURUSD", "USDJPY"}


def test_terms_quote_all_three_publishers() -> None:
    ev = A.TERMS_EVIDENCE[A.NET_LIQ_ID]
    assert A.TERMS[A.NET_LIQ_ID][0] == "confirmed" == SRC.terms
    assert "public domain" in ev["terms_quote"]
    assert "commercial purposes" in ev["tga_terms_quote"]
    assert "through an automated process or device" in ev["rrp_terms_quote"]
    assert ev["checked_at"] == "2026-10-14"


# ---------------------------------------------------------------------------- HELD routes
def test_held_routes_carry_a_quote_and_have_no_source_row(tmp_path: Path) -> None:
    assert not any("cmegroup.com" in s.url or "cboe.com" in s.url for s in A.SOURCES)
    assert set(A.HELD_ROUTES) == {"cme_margin_changes", "cn_credit_contagion",
                                  "cboe_delayed_index_values", "us_finra_regsho_short_volume",
                                  "gb_adzuna_vacancies", "congress_trades",
                                  # pass 6 (F2, F4 and the FINRA margin route), all HELD
                                  "comex_warehouse_stocks", "lme_warehouse_stocks",
                                  "jpx_short_selling_ratio", "jpx_margin_balances",
                                  "jp_tocom_settlements", "us_finra_margin_statistics",
                                  # the China exchange holds, fence rows since the pass-6 delta
                                  "cnx_shfe", "cnx_ine", "cnx_dce", "cnx_czce", "cnx_gfex",
                                  "cnx_cffex"}
    for rid, h in A.HELD_ROUTES.items():
        # a quoted clause cites an https terms page; only the four UNREAD China-exchange rows
        # (no clause at all) cite the http page that could not be read, verbatim from their
        # 2026-10-06 evidence. cnx_shfe and cnx_ine quote clauses, so they cite https.
        unread_cnx = ("cnx_dce", "cnx_czce", "cnx_gfex", "cnx_cffex")
        scheme = ("https://", "http://") if rid in unread_cnx else ("https://",)
        assert h["verdict"] == "HELD" and h["terms_url"].startswith(scheme), rid
        assert h["terms_quote"] and h["reason"] and h["unblock"], rid
        assert rid not in A.BY_ID and rid not in A.TERMS, rid           # never fetched
    from libs.data import terms_fence as tf
    for rid in A.HELD_ROUTES:                               # ONE register: each is a fence row
        row = tf.SOURCE_POLICY[rid]
        assert row["held_route"] and row["status"] == tf.IDEAS_ONLY and not row["hosts"], rid
        assert A.HELD_ROUTES[rid]["reason"] == row["why"], rid
    assert set(A.HELD_ROUTES) == tf.HELD_ROUTE_KEYS
    assert "derivative works" in A.HELD_ROUTES["cme_margin_changes"]["terms_quote"]
    assert "prior written consent" in A.HELD_ROUTES["cboe_delayed_index_values"]["terms_quote"]
    rep = A.run(A.Paths(tmp_path / "desk"), fixtures=FIX, donate=False, dry_run=True,
                now=datetime(2026, 9, 30, 12, tzinfo=UTC))
    assert set(rep["held_routes"]) == set(A.HELD_ROUTES)
    assert rep["sources"][A.NET_LIQ_ID]["series"].get("net_liquidity", 0) >= 1
