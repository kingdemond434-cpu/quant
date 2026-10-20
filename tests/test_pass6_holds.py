"""Pass-6 lanes, on fixtures, with no network. Every source was terms-gated FIRST and all are HELD.

F2  COMEX registered vs eligible warehouse stocks (CME ToU s.12, s.8(vi) and the Data Terms of
    Use; the delivery-report page carries no licence of its own) and the LME cancelled-warrant
    share (LME website terms 3.1.2 / 3.1.11) are HELD.
F4  JPX short-selling ratio and margin balances are HELD on JPX's site terms (secondary use and
    redistribution barred for any purpose without permission; automated retrieval discouraged).
    The OSE settlements route the asia collector pointed at jpx.co.jp is held on the same terms.
SF1 the free-stack exchange holds (cnx_*) are fence rows (the roster's own `terms` /
    `terms_evidence` fields, a second register, are gone; auditor ruling 2026-10-14); the hold
    comes from the fence row, lifting the row lifts it, and each carries a missed-growth line
    with past conversion from the cursor.
CME the cme_margin_changes row's url_patterns cover the clearing-advisory and performance-bond
    routes and no other cmegroup.com page.
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
    "https://www.cmegroup.com/CmeWS/mvc/Metals/GetDepositary/GC/": "comex_warehouse_stocks",
    "https://www.cmegroup.com/market-data/delayed-quotes/metals/warehouse-reports.html":
        "comex_warehouse_stocks",
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


CME_MARGIN = ("https://www.cmegroup.com/notices/clearing/2026/10/Chadv26-312.html",
              "https://www.cmegroup.com/notices/clearing/2026/10/Chadv26-312.pdf",
              "https://www.cmegroup.com/notices.html",
              "https://www.cmegroup.com/clearing/margins/outright-vol-scans.html",
              "https://www.cmegroup.com/clearing/risk-management/performance-bond-requirements.html",
              "https://www.cmegroup.com/solutions/risk-management/performance-bonds-margins.html",
              "https://www.cmegroup.com/CmeWS/mvc/Margins/OUTRIGHT?sortField=exchange")


@pytest.mark.parametrize("url", CME_MARGIN)
def test_cme_margin_advisory_routes_resolve_to_the_margin_row(url: str) -> None:
    assert "url_patterns" in tf.SOURCE_POLICY["cme_margin_changes"]
    assert tf.input_source(url) == "cme_margin_changes"
    assert tf.policy_of_url(url)["status"] == tf.IDEAS_ONLY


@pytest.mark.parametrize("url", [
    "https://www.cmegroup.com/markets/metals.html",
    "https://www.cmegroup.com/market-data/volume-open-interest.html",
    "https://www.cmegroup.com/tools-information/calendars.html",
    "https://www.cmegroup.com/insights/economic-research.html",
    "https://www.cmegroup.com/notices/market-regulation/2026/10/x.html"])
def test_other_cmegroup_pages_are_not_the_margin_row(url: str) -> None:
    assert tf.input_source(url) is None
    assert tf.policy_of_url(url)["status"] == tf.PUBLIC_PAGE


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
    monkeypatch.setattr(ac, "polite_urlopen", _no_network)
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
CNX = ("cnx_shfe", "cnx_ine", "cnx_dce", "cnx_czce", "cnx_gfex", "cnx_cffex")
_TERMS_FIELDS = {"terms_url", "terms_quote", "terms_evidence", "terms_judgement"}


def test_no_second_register_in_the_free_stack_roster() -> None:
    """Auditor ruling 2026-10-14: no roster row holds a source on its own terms. A `terms` field
    survives only as the Google Trends SEARCH-term list (not a licence word); every licence hold
    is a fence row the roster points at with `terms_policy`."""
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    for r in doc["sources"]:
        assert not _TERMS_FIELDS & set(r), r["id"]
        if "terms" in r:
            assert r["kind"] == "gtrends" and isinstance(r["terms"], list), r["id"]
        if "terms_policy" in r:
            assert f"SOURCE_POLICY[{r['id']}]" in r["terms_policy"], r["id"]
            assert tf.held_on_terms(r["id"]), r["id"]
    held = {r["id"] for r in doc["sources"] if tf.held_on_terms(r["id"])}
    assert held >= {*CNX, "congress_trades"}
    for sid in CNX:
        row = tf.SOURCE_POLICY[sid]
        assert row["held_route"] and row["sources"] == (sid,) and row["hosts"] == (), sid
        assert row["wanted"] and row["why"] and row["unblock"] and row["robots"], sid
        assert row["terms"].get("clauses") or row["terms"].get("unread"), sid
    assert tf.terms_verdict("cnx_shfe") == tf.terms_verdict("cnx_ine") == "refused"
    assert {tf.terms_verdict(s) for s in CNX[2:]} == {"to_confirm"}
    assert "电子抓取系统" in tf.SOURCE_POLICY["cnx_shfe"]["terms"]["clauses"]["commercial_bar"]
    assert "slider-captcha" in tf.SOURCE_POLICY["cnx_ine"]["terms"]["unread"]["ine.cn"]


def test_cnx_hold_comes_from_the_fence_row_and_lifting_it_lifts_the_hold(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import free_stack_cnx as cnx
    rep = _cnx_pass(tmp_path / "a")
    assert rep["per_source"]["cnx_dce"]["status"] == "HELD_ON_TERMS"
    # the box's unblock: flip the FENCE row (no roster field exists to flip)
    monkeypatch.setitem(tf.SOURCE_POLICY, "cnx_dce", {
        **tf.SOURCE_POLICY["cnx_dce"], "held_route": False, "status": tf.PUBLIC_PAGE,
        "terms": {"url": "http://www.dce.com.cn/", "checked_at": "2026-10-14",
                  "clauses": {"grant": "SYNTHETIC TEST GRANT: automated research use permitted"}}})
    assert not tf.held_on_terms("cnx_dce") and tf.terms_verdict("cnx_dce") == "confirmed"
    assert cnx.terms_of({"id": "cnx_dce"}) == "confirmed"
    from libs.data import free_stack as cnx_fs
    calls: list[str] = []

    def fetch(url: str, headers: Any = None, body: Any = None) -> bytes:
        calls.append(url)
        raise cnx_fs.FetchError("http_404", url)
    h = cnx.fetch_cn_exchange(fetch, {"id": "cnx_dce", "exchange": "dce", "days_per_pass": 1},
                              {}, NOW)
    assert calls and h.status != "BLOCKED_ON_TERMS"            # the gate opened: it requested
    lines = {ln["source"] for ln in _cnx_pass(tmp_path / "b")["missed_growth_lines"]}
    assert "cnx_dce" not in lines and "cnx_shfe" in lines      # no hold, no hold line



def _cnx_pass(tmp_path: Path, cursor: dict[str, Any] | None = None) -> dict[str, Any]:
    from free_stack_hunter import Store, run
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    rows = [r for r in doc["sources"] if r["id"] in CNX]
    assert {r["id"] for r in rows} == set(CNX)
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
    for sid in CNX:
        ln = lines[sid]
        assert ln["kind"] == "terms_hold" and ln["status"] == "HELD_ON_TERMS", sid
        assert ln["delta_elogw"] == "UNMEASURED", sid
        assert ln["policy_status"] == tf.IDEAS_ONLY, sid
        assert ln["terms_url"] == tf.SOURCE_POLICY[sid]["terms"]["url"], sid
        assert "no measured conversion on record" in ln["cause"], sid
        assert rep["per_source"][sid]["status"] == "HELD_ON_TERMS", sid
        assert f"terms_fence {sid}" in rep["per_source"][sid]["last_error"], sid
    assert "NON-COMMERCIAL" in lines["cnx_shfe"]["cause"]


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


# ============================================================================ audit 27d186241
_GOLD = "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"


@pytest.mark.parametrize("url,row", [
    ("https://www.cmegroup.com//delivery_reports/Gold_Stocks.xls", "comex_warehouse_stocks"),
    ("https://www.cmegroup.com/./delivery_reports/Gold_Stocks.xls", "comex_warehouse_stocks"),
    ("https://www.cmegroup.com/x/../delivery_reports/Gold_Stocks.xls", "comex_warehouse_stocks"),
    ("https://www.cmegroup.com/delivery%5Freports/Gold_Stocks.xls", "comex_warehouse_stocks"),
    ("https://www.cmegroup.com/%64elivery_reports/Gold_Stocks.xls", "comex_warehouse_stocks"),
    ("https://www.cmegroup.com/delivery%255Freports/Gold_Stocks.xls", "comex_warehouse_stocks"),
    ("https://www.jpx.co.jp/markets/statistics-equities/short-selling",
     "jpx_short_selling_ratio"),
    ("https://www.jpx.co.jp/markets/statistics-equities/margin", "jpx_margin_balances"),
    ("https://www.jpx.co.jp/english/markets/derivatives", "jp_tocom_settlements"),
    ("https://www.cmegroup.com/notices//clearing/2026/10/Chadv26-312.html", "cme_margin_changes"),
])
def test_a_route_cannot_escape_its_pattern_by_spelling(url: str, row: str) -> None:
    """MUST-FIX 1: the path is percent-decoded, `//` collapsed, dot segments removed and a
    folder with no trailing slash matched as the folder, so every spelling of the same
    resource names the held row."""
    assert tf.input_source(url) == row
    assert tf.input_source(f"https://web.archive.org/web/2026/{url}") == row


def test_normalization_does_not_widen_a_route() -> None:
    for url in ("https://www.cmegroup.com/delivery_reports/../markets/metals.html",
                "https://www.jpx.co.jp/markets/statistics-equities/margin-x/index.html",
                "https://www.jpx.co.jp/markets/statistics-equities/short-selling/../index.html"):
        assert tf.input_source(url) is None, url


def test_the_lme_hold_is_site_wide_by_clause_3_1_11() -> None:
    """SHOULD-FIX (documented choice): clause 3.1.11 bars automated download of Information
    'from any LME website', so every lme.com route is held as live input -- and, IDEAS_ONLY,
    still readable for ideas."""
    q = tf.SOURCE_POLICY["lme_warehouse_stocks"]["terms"]["clauses"]["3.1.11"]
    assert "from any LME website" in q
    for url in ("https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports",
                "https://www.lme.com/en/metals/non-ferrous/lme-copper",
                "https://lme.com/", "https://www.lme.com/en/news"):
        assert tf.input_source(url) == "lme_warehouse_stocks", url
        assert tf.platform_of_url(url) is None, url              # ideas still mined
    assert tf.input_source("https://www.lmecopper.example/") is None


def test_asia_collector_keeps_the_pre_hold_record_on_every_held_pass(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SHOULD-FIX: `last_status_before_hold` is persisted in collector_state, so the second and
    later held passes still carry the past conversion."""
    import asia_collector as ac
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.setattr(ac, "polite_urlopen", _no_network)
    monkeypatch.setattr(ac, "_robots_allows", _no_network)
    reg, state, out = tmp_path / "reg.json", tmp_path / "state.json", tmp_path / "out.json"
    reg.write_text(json.dumps({"sources": [{"id": "comex_warehouse", "url": _GOLD,
                                            "expect": "csv", "access": "public",
                                            "cadence": "daily"}]}), "utf-8")
    state.write_text(json.dumps({"comex_warehouse": {"last_status": "COLLECTED"}}), "utf-8")
    monkeypatch.setattr(ac, "REGISTRY", reg)
    monkeypatch.setattr(ac, "STATE", state)
    monkeypatch.setattr(ac, "OUT", out)
    for _ in range(3):
        assert ac.main(["--id", "comex_warehouse"]) == 0
        doc = json.loads(out.read_text("utf-8"))
        ln = next(x for x in doc["missed_growth_lines"] if x["registry_id"] == "comex_warehouse")
        assert ln["past_conversion"]["last_status_before_hold"] == "COLLECTED"
        assert ln["delta_elogw"] == "UNMEASURED"
        st = json.loads(state.read_text("utf-8"))["comex_warehouse"]
        assert st["last_status"] == tf.IDEAS_ONLY
        assert st["last_status_before_hold"] == "COLLECTED"


# ============================================================================ audit e5a1526f3
#: MUST-FIX 1: the asia_collector registry rows that fetch the China exchanges' own data under
#: their own ids (asia_sources.json indices 12-19 and 48-52) -> the exchange's held row.
CN_ASIA_ROWS = {
    "shfe_daily": "cnx_shfe", "shfe_warehouse": "cnx_shfe", "shfe_member_rank": "cnx_shfe",
    "shfe_delivery": "cnx_shfe", "ine_crude": "cnx_ine",
    "dce_daily": "cnx_dce", "dce_member_rank": "cnx_dce",
    "czce_daily": "cnx_czce", "czce_member_rank": "cnx_czce", "gfex_daily": "cnx_gfex",
    "cffex_daily": "cnx_cffex", "cffex_member_rank": "cnx_cffex",
    "cffex_option_stats": "cnx_cffex",
}


def _asia_rows() -> dict[str, dict[str, Any]]:
    doc = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    return {r["id"]: r for r in doc["sources"]}


def test_the_thirteen_cn_exchange_asia_rows_are_the_audited_indices() -> None:
    doc = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    ids = [doc["sources"][i]["id"] for i in (*range(12, 20), *range(48, 53))]
    assert sorted(ids) == sorted(CN_ASIA_ROWS)


@pytest.mark.parametrize("rid,row", sorted(CN_ASIA_ROWS.items()))
def test_cn_exchange_asia_rows_resolve_to_the_held_row_and_make_no_request(
        rid: str, row: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import asia_collector as ac
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    monkeypatch.setattr(ac, "polite_urlopen", _no_network)
    monkeypatch.setattr(ac, "_robots_allows", _no_network)
    src = _asia_rows()[rid]
    assert tf.input_source(ac._resolve_url(src), rid) == row
    rec = ac.collect_one(src)
    assert rec["fetched"] == 0 and rec["status"] == tf.IDEAS_ONLY and rec["source"] == row
    assert tf.held_on_terms(row)
    assert tf.platform_of_url(src["url"].replace("{", "").replace("}", "")) is None  # ideas


def test_cnx_rows_hold_their_whole_exchange_host_each_on_its_own_row() -> None:
    """SHFE's commercial bar covers any content of the website (site-wide, like LME 3.1.11);
    INE is judged by its own row; the unread exchanges hold the host because UNREAD never
    permits. Every row stays IDEAS_ONLY."""
    assert "本网站的任何内容" in tf.SOURCE_POLICY["cnx_shfe"]["terms"]["clauses"]["commercial_bar"]
    for url, row in (("https://www.shfe.com.cn/", "cnx_shfe"),
                     ("https://shfe.com.cn/news/x.html", "cnx_shfe"),
                     ("https://www.ine.cn/data/dailydata/kx/pm20261013.dat", "cnx_ine"),
                     ("http://www.dce.com.cn/publicweb/quotesdata/x.html", "cnx_dce"),
                     ("http://www.czce.com.cn/cn/x.htm", "cnx_czce"),
                     ("http://www.gfex.com.cn/u/x", "cnx_gfex"),
                     ("http://www.cffex.com.cn/sj/ccpm/202610/13/IF.xml", "cnx_cffex")):
        assert tf.input_source(url) == row, url
        assert tf.SOURCE_POLICY[row]["status"] == tf.IDEAS_ONLY
        assert tf.platform_of_url(url) is None, url               # ideas still mined


def test_cnx_host_holds_do_not_catch_other_hosts() -> None:
    for url in ("https://www.sge.com.cn/sjzx/mrhq", "https://www.chinamoney.com.cn/r/x.json",
                "https://mine.cn/", "https://www.notshfe.com.cn/", "https://shfe.com.cn.example/",
                "https://www.example.org/www.shfe.com.cn/", "https://www.dce.com/",
                "https://www.cffex.com.cn.example.org/"):
        assert tf.input_source(url) is None, url


# ---------------------------------------------------------------- MUST-FIX 2: redirect hops
_HELD_TARGETS = {
    "https://www.jpx.co.jp/markets/statistics-equities/short-selling/x.xls":
        "jpx_short_selling_ratio",
    "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls": "comex_warehouse_stocks",
    "https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports":
        "lme_warehouse_stocks",
}
_START = "https://data.example.org/moved"
_UNHELD = "https://data.example.org/new-home.csv"


class _FakeWeb(urllib.request.BaseHandler):
    """Serves `_START` as a 302 to `self.target` and any other URL as a 200 body; no socket."""

    handler_order = 100

    def __init__(self, target: str) -> None:
        self.target = target
        self.served: list[str] = []

    def https_open(self, req: urllib.request.Request) -> Any:
        import email.message
        import io
        import urllib.response
        self.served.append(req.full_url)
        hdrs = email.message.Message()
        if req.full_url == _START:
            hdrs["Location"] = self.target
            r = urllib.response.addinfourl(io.BytesIO(b""), hdrs, req.full_url, 302)
            r.msg = "Found"
            return r
        hdrs["Content-Type"] = "text/csv"
        r = urllib.response.addinfourl(io.BytesIO(b"a,b\n1,2\n"), hdrs, req.full_url, 200)
        r.msg = "OK"
        return r

    http_open = https_open


def _patch_web(monkeypatch: pytest.MonkeyPatch, target: str) -> _FakeWeb:
    web = _FakeWeb(target)
    real = tf.guarded_opener

    def opener(context: Any = None, *handlers: Any) -> Any:
        return real(context, web, *handlers)

    monkeypatch.setattr(tf, "guarded_opener", opener)
    return web


@pytest.mark.parametrize("target,row", sorted(_HELD_TARGETS.items()))
def test_a_302_into_a_held_route_is_refused_for_live_input(
        target: str, row: str, monkeypatch: pytest.MonkeyPatch) -> None:
    web = _patch_web(monkeypatch, target)
    with pytest.raises(tf.TermsFenced) as ei:
        tf.guarded_urlopen(_START, live_input=True)
    assert ei.value.platform == row and ei.value.status == tf.IDEAS_ONLY
    assert web.served == [_START]                       # the held target was never requested


@pytest.mark.parametrize("target,row", sorted(_HELD_TARGETS.items()))
def test_asia_collector_and_free_stack_refuse_a_302_into_a_held_route(
        target: str, row: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import asia_collector as ac

    from libs.data import free_stack as fs
    web = _patch_web(monkeypatch, target)
    monkeypatch.setattr(ac, "_robots_allows", lambda url, *a, **k: (True, "fixture"))
    rec = ac.collect_one({"id": "moved_series", "url": _START, "expect": "any",
                          "access": "public", "cadence": "daily"})
    assert rec["status"] == tf.IDEAS_ONLY and rec["source"] == row and rec["redirected"]
    assert rec["fetched"] == 0
    with pytest.raises(fs.FetchError) as ei:
        fs.http_fetch(_START)
    assert row in ei.value.detail
    assert target not in web.served


def test_a_302_to_an_unheld_page_still_follows(monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import free_stack as fs
    web = _patch_web(monkeypatch, _UNHELD)
    with tf.guarded_urlopen(_START, live_input=True) as r:
        assert r.read() == b"a,b\n1,2\n"
        assert r.redirects == [(302, _START, _UNHELD)]
    assert fs.http_fetch(_START) == b"a,b\n1,2\n"
    assert web.served[-2:] == [_START, _UNHELD]


def test_an_ideas_fetch_still_follows_a_302_into_an_ideas_only_route(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Ideas mining is untouched: without `live_input` a 302 into an IDEAS_ONLY (not held)
    route is followed, as before."""
    target = "https://www.lme.com/en/news"
    _patch_web(monkeypatch, target)
    with tf.guarded_urlopen(_START) as r:
        assert r.redirects == [(302, _START, target)]


# ---------------------------------------------------------------- SHOULD-FIX: ;params
@pytest.mark.parametrize("url,row", [
    ("https://www.jpx.co.jp/markets;v=1/statistics-equities/short-selling/",
     "jpx_short_selling_ratio"),
    ("https://www.jpx.co.jp/markets/statistics-equities/short-selling;x=1/index.html",
     "jpx_short_selling_ratio"),
    ("https://www.jpx.co.jp/markets/statistics-equities;jsessionid=A1/margin/index.html",
     "jpx_margin_balances"),
    ("https://www.cmegroup.com/delivery_reports;v=2/Gold_Stocks.xls", "comex_warehouse_stocks"),
])
def test_a_segment_param_cannot_escape_a_route(url: str, row: str) -> None:
    assert tf.input_source(url) == row


def test_stripping_params_does_not_widen_a_route() -> None:
    assert tf.input_source(
        "https://www.jpx.co.jp/markets/statistics-equities/short-selling-x;v=1/") is None
    assert tf.input_source("https://www.jpx.co.jp/markets/statistics-equities;x=/index.html") \
        is None


# ------------------------------------- audit cf305e3d2 SHOULD-FIX 1: the other live fetchers
class _RedirectEverything(urllib.request.BaseHandler):
    """Every URL but `target` is a 302 to `target`; `target` would be a 200. No socket."""

    handler_order = 100

    def __init__(self, target: str) -> None:
        self.target = target
        self.served: list[str] = []

    def https_open(self, req: urllib.request.Request) -> Any:
        import email.message
        import io
        import urllib.response
        self.served.append(req.full_url)
        hdrs = email.message.Message()
        if req.full_url != self.target:
            hdrs["Location"] = self.target
            r = urllib.response.addinfourl(io.BytesIO(b""), hdrs, req.full_url, 302)
            r.msg = "Found"
            return r
        r = urllib.response.addinfourl(io.BytesIO(b"[]"), hdrs, req.full_url, 200)
        r.msg = "OK"
        return r

    http_open = https_open


def _live_fetchers() -> list[tuple[str, Any]]:
    import axis_ingest
    import fetch_futures_curves
    import free_data

    from libs.data import cot_source
    return [
        ("free_data._get", lambda: free_data._get(_START)),
        ("free_data._get ideas-first (Yahoo)", lambda: free_data._get(_START, live_input=False)),
        ("alt_proxies.http_get", lambda: A.http_get(_START)),
        ("cot_source._get", lambda: cot_source._get(_START)),
        ("axis_ingest._fetch", lambda: axis_ingest._fetch(_START)),
        ("fetch_futures_curves.fetch_contract",
         lambda: fetch_futures_curves.fetch_contract("GCZ26.CMX")),
    ]


@pytest.mark.parametrize("which", range(6))
@pytest.mark.parametrize("target,row", sorted(_HELD_TARGETS.items()))
def test_every_live_fetcher_refuses_a_302_into_a_held_route(
        which: int, target: str, row: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """free_data (macro_desk / news_desk), alt_proxies.http_get (vintage store), cot_source,
    axis_ingest and fetch_futures_curves: a 302 into a held IDEAS_ONLY route is refused and the
    held target is never requested."""
    web = _RedirectEverything(target)
    real = tf.guarded_opener

    def opener(context: Any = None, *handlers: Any, **kw: Any) -> Any:
        return real(context, web, *handlers, **kw)

    monkeypatch.setattr(tf, "guarded_opener", opener)
    name, call = _live_fetchers()[which]
    with pytest.raises(tf.TermsFenced) as ei:
        call()
    assert ei.value.platform == row, name
    assert target not in web.served, name
    assert len(web.served) == 1, name


# ------------------------------------- audit cf305e3d2 SHOULD-FIX 2: `;` after decoding
@pytest.mark.parametrize("url", [
    "https://www.jpx.co.jp/markets/statistics-equities/short-selling/..;x/x.xls",
    "https://www.jpx.co.jp/markets/statistics-equities/short-selling/..%3Bx/x.xls",
    "https://www.jpx.co.jp/markets/statistics-equities/short-selling/..%253Bx/x.xls",
    "https://www.jpx.co.jp/markets/statistics-equities/short-selling/.%3Bx/x.xls",
])
def test_an_encoded_or_raw_param_on_a_dot_segment_cannot_pop_out_of_a_held_folder(
        url: str) -> None:
    assert tf.input_source(url) == "jpx_short_selling_ratio"
