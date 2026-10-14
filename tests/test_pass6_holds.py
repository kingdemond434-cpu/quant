"""Pass-6 lanes, on fixtures, with no network. Every source was terms-gated FIRST and all are HELD.

F2  COMEX registered vs eligible warehouse stocks (CME ToU s.12, s.8(vi) and the Data Terms of
    Use; the delivery-report page carries no licence of its own) and the LME cancelled-warrant
    share (LME website terms 3.1.2 / 3.1.11) are HELD.
F4  JPX short-selling ratio and margin balances are HELD on JPX's site terms (secondary use and
    redistribution barred for any purpose without permission; automated retrieval discouraged).
    The OSE settlements route the asia collector pointed at jpx.co.jp is held on the same terms.
SF1 the free-stack exchange roster holds (cnx_*, held on the roster's own `terms`) carry
    missed-growth lines, past conversion from the cursor.
SF2 the FINRA margin-statistics route (US pack) is HELD on FINRA's site-wide ToU: IDEAS_ONLY,
    never live input.
Every hold is ONE terms_fence row (held_route) with a verbatim clause and a missed-growth line.
No parser or PIT stamp was built: no source cleared its terms.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
PASS6_HELD = ("comex_warehouse_stocks", "lme_warehouse_stocks", "jpx_short_selling_ratio",
              "jpx_margin_balances", "jp_tocom_settlements", "us_finra_margin_statistics")
#: route URL -> the held row it must resolve to (the live-input check)
ROUTES = {
    "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls": "comex_warehouse_stocks",
    "https://www.cmegroup.com/delivery_reports/Copper_Stocks.xls": "comex_warehouse_stocks",
    "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls": "comex_warehouse_stocks",
    "https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports":
        "lme_warehouse_stocks",
    "https://www.jpx.co.jp/markets/statistics-equities/short-selling/index.html":
        "jpx_short_selling_ratio",
    "https://www.jpx.co.jp/english/markets/statistics-equities/margin/index.html":
        "jpx_margin_balances",
    "https://www.jpx.co.jp/english/markets/derivatives/": "jp_tocom_settlements",
    "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics":
        "us_finra_margin_statistics",
    "https://www.finra.org/sites/default/files/2026-09/margin-statistics.xlsx":
        "us_finra_margin_statistics",
}


def _no_network(*a: Any, **k: Any) -> Any:
    raise AssertionError("network touched")


# ============================================================================ the fence rows
def test_each_pass6_hold_is_one_fence_row_with_a_verbatim_clause() -> None:
    for sid in PASS6_HELD:
        row = tf.SOURCE_POLICY[sid]
        assert row["held_route"] is True and row["status"] == tf.IDEAS_ONLY, sid
        assert row["hosts"] == () and row["url_level"] is False, sid
        assert row["sources"] == (sid,), sid
        assert row["wanted"] and row["why"] and row["unblock"] and row["robots"], sid
        t = row["terms"]
        assert t["url"].startswith("https://") and t["checked_at"] == "2026-10-14", sid
        assert t["clauses"] and all(len(c) > 40 for c in t["clauses"].values()), sid
        assert tf.terms_state(sid) == "READ" and tf.held_on_terms(sid), sid
        assert tf.input_source(sid) == sid, sid
        assert sid in tf.HELD_ROUTE_KEYS and A.HELD_ROUTES[sid]["verdict"] == "HELD", sid
    q = {sid: " ".join(tf.SOURCE_POLICY[sid]["terms"]["clauses"].values()) for sid in PASS6_HELD}
    assert "derivative works" in q["comex_warehouse_stocks"]
    assert "machine learning" in q["comex_warehouse_stocks"]
    assert "personal use for non-commercial purposes" in q["comex_warehouse_stocks"]
    assert "scrape or otherwise download Information" in q["lme_warehouse_stocks"]
    assert "Derived Information" in q["lme_warehouse_stocks"]
    for jp in ("jpx_short_selling_ratio", "jpx_margin_balances", "jp_tocom_settlements"):
        assert "二次利用及び再配信はできません" in q[jp] and "自動取得" in q[jp], jp
        assert "secondary use of information" in q[jp], jp
    assert "non-commercial personal or professional use" in q["us_finra_margin_statistics"]
    assert "develop or create a database" in q["us_finra_margin_statistics"]


def test_one_register_no_second_table() -> None:
    """The holds live in the fence only: alt_proxies has no Source/TERMS row for any of them,
    and the view it reports is a read of the fence row."""
    for sid in PASS6_HELD:
        assert sid not in A.BY_ID and sid not in A.TERMS and sid not in A.TERMS_EVIDENCE, sid
        assert A.HELD_ROUTES[sid]["reason"] == tf.SOURCE_POLICY[sid]["why"], sid
    assert not any(h in s.url for s in A.SOURCES
                   for h in ("cmegroup.com", "lme.com", "jpx.co.jp", "finra.org"))


@pytest.mark.parametrize("url,row", sorted(ROUTES.items()))
def test_every_route_url_resolves_to_its_held_row(url: str, row: str) -> None:
    assert tf.input_source(url) == row
    assert tf.policy_of_url(url)["status"] == tf.IDEAS_ONLY
    # an archived copy of the route is the route
    assert tf.input_source(f"https://web.archive.org/web/2026/{url}") == row


def test_route_rows_do_not_capture_the_rest_of_the_host() -> None:
    for url in ("https://www.cmegroup.com/markets/metals.html",
                "https://www.jpx.co.jp/markets/statistics-equities/index.html",
                "https://www.finra.org/rules-guidance"):
        assert tf.input_source(url) is None, url
        assert tf.policy_of_url(url)["status"] == tf.PUBLIC_PAGE, url


# ============================================================================ 0 requests
def test_alt_proxies_makes_no_request_for_a_pass6_hold(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    rep = A.run(A.Paths(tmp_path / "desk"), fixtures=FIX, donate=False, dry_run=True, now=NOW)
    for sid in PASS6_HELD:
        assert sid not in rep["sources"] and rep["held_routes"][sid]["verdict"] == "HELD", sid


@pytest.mark.parametrize("rid", ["comex_warehouse", "lme_warehouse", "jp_tocom_settlements"])
def test_asia_collector_registry_rows_on_held_routes_make_no_request(
        rid: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The asia collector's registry pointed at CME's delivery reports, LME's reports page and
    JPX's derivatives page; each URL now names its held row, so nothing is requested, robots.txt
    included."""
    import asia_collector as ac
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.setattr(ac, "fenced_urlopen", _no_network)
    monkeypatch.setattr(ac, "_robots_allows", _no_network)
    doc = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == rid)
    rec = ac.collect_one(row)
    assert rec["fetched"] == 0 and rec["status"] == tf.IDEAS_ONLY
    assert tf.held_on_terms(rec["source"])
    lines = ac.held_missed_growth_lines([rec], {})
    assert len(lines) == 1 and lines[0]["source"] == rec["source"]
    assert lines[0]["delta_elogw"] == "UNMEASURED" and lines[0]["registry_id"] == rid
    assert "no measured conversion on record" in lines[0]["cause"]
    # a source the collector reached before the hold: the last status is its past conversion
    prior = {rid: {"last_status": "COLLECTED"}}
    ln = ac.held_missed_growth_lines([rec], prior)[0]
    assert ln["past_conversion"]["last_status_before_hold"] == "COLLECTED"


# ============================================================================ missed growth
def test_alt_proxies_report_carries_a_missed_growth_line_per_pass6_hold(tmp_path: Path) -> None:
    rep = A.run(A.Paths(tmp_path / "desk"), fixtures=FIX, donate=False, dry_run=True, now=NOW)
    lines = {ln["source"]: ln for ln in rep["missed_growth_lines"]}
    for sid in PASS6_HELD:
        ln = lines[sid]
        assert ln["kind"] == "terms_hold" and ln["status"] == "HELD_ON_TERMS", sid
        assert ln["delta_elogw"] == "UNMEASURED" and ln["cause"], sid
        assert ln["terms_url"] == tf.SOURCE_POLICY[sid]["terms"]["url"], sid


# ============================================================================ SF1 cnx holds
def _cnx_pass(tmp_path: Path, cursor: dict[str, Any] | None = None) -> dict[str, Any]:
    from free_stack_hunter import Store, run
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    rows = [r for r in doc["sources"] if r.get("terms") in ("refused", "to_confirm")]
    assert {r["id"] for r in rows} >= {"cnx_shfe", "cnx_ine", "cnx_dce"}
    tmp_path.mkdir(parents=True, exist_ok=True)
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"sources": rows}), "utf-8")
    store = Store(tmp_path)
    if cursor is not None:
        store.cursor.parent.mkdir(parents=True, exist_ok=True)
        store.cursor.write_text(json.dumps(cursor), "utf-8")
    return run(budget_s=30, fetch=lambda *a: (_ for _ in ()).throw(AssertionError("fetched")),
               store=store, roster=roster, now=NOW, live=False)


def test_cnx_roster_holds_carry_missed_growth_lines(tmp_path: Path) -> None:
    rep = _cnx_pass(tmp_path / "a")
    lines = {ln["source"]: ln for ln in rep["missed_growth_lines"]}
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    held = {r["id"]: r for r in doc["sources"] if r.get("terms") in ("refused", "to_confirm")}
    assert set(held) <= set(lines)
    for sid, row in held.items():
        ln = lines[sid]
        assert ln["kind"] == "terms_hold" and ln["status"] == "HELD_ON_TERMS", sid
        assert ln["delta_elogw"] == "UNMEASURED", sid
        assert ln["policy_status"] == f"roster_terms:{row['terms']}", sid
        assert ln["terms_url"] == row["terms_evidence"]["terms_url"], sid
        assert "no measured conversion on record" in ln["cause"], sid
    assert "非商业" in lines["cnx_shfe"]["cause"] or "NON-COMMERCIAL" in lines["cnx_shfe"]["cause"]


def test_cnx_hold_past_conversion_comes_from_the_cursor(tmp_path: Path) -> None:
    rep = _cnx_pass(tmp_path / "b", {"cnx_shfe": {
        "attempts": 12, "successes": 7, "obs_total": 3400, "last_success": "2026-10-05T00:00:00Z"}})
    ln = next(x for x in rep["missed_growth_lines"] if x["source"] == "cnx_shfe")
    assert ln["past_conversion"] == {"attempts": 12, "successes": 7, "obs_total": 3400,
                                     "last_success": "2026-10-05T00:00:00Z"}
    assert ln["delta_elogw"] == "UNMEASURED" and "past_conversion" in ln["cause"]


# ============================================================================ SF2 FINRA margin
def test_us_pack_finra_margin_route_is_never_live_input() -> None:
    from research.countries.us import pack as us
    row = next(p for p in us.POSITIONING_SOURCES if "FINRA margin" in p["name"])
    assert tf.input_source(row["root"]) == "us_finra_margin_statistics" == row["terms_fence"]
    assert row["live_input"] is False and row["available"] is False
    assert "IDEAS_ONLY" in row["licence"]
    # still surfaced as an idea ground: the source class keeps its root, labelled
    sc = next(c for c in us.SOURCE_CLASSES if c["id"] == "us_finra_retail_flow")
    assert any("margin-statistics" in r for r in sc["roots"])
    assert "us_finra_margin_statistics" in sc["licence"]
    # IDEAS_ONLY is not a fetch refusal: reading the page for ideas stays allowed
    assert tf.platform_of_url(row["root"]) is None
    line = tf.held_missed_growth("us_finra_margin_statistics")
    assert line["delta_elogw"] == "UNMEASURED" and line["cause"]
