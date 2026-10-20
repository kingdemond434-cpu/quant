"""Pass-5 lanes, on fixtures, with no network.

F4  HKMA interbank liquidity (Convertibility Undertaking flow, Aggregate Balance, HIBOR) through
    alt_proxies' hourly leg and exogenous_conditioner path.
N6  the Wikipedia attention row extended to ja/tr/es/pt/ko currency and crisis articles, under
    the Wikimedia User-Agent policy.
GAP1 USAJOBS posting counts (key and e-mail in headers only, first-seen PIT); Adzuna HELD.
F2  FINRA Reg SHO short volume HELD on FINRA's own terms.
GAP2 congressional PTR trades parsed (ticker, side, band, transaction and filing dates) and the
    congress row HELD on the statute the disclosure gate prints.
The three holds are rows of ONE register (libs/data/terms_fence.SOURCE_POLICY, held_route), read
by alt_proxies.HELD_ROUTES and by free_stack_hunter; each carries a missed-growth line.
GAP3 deep_forest's non-Bing site-index route (sitemap, else Common Crawl CDX), robots-gated.

Every fixture is SYNTHETIC (values illustrative, never the publisher's).
"""
from __future__ import annotations

import json
import sys
import urllib.error
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from research import alt_proxies as A  # noqa: E402
from research import deep_forest_miner as D  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
LIVE = ("hk_hkma_liquidity", "us_usajobs_postings")
HELD = ("us_finra_regsho_short_volume", "gb_adzuna_vacancies")
#: Every pass-5 hold, as a terms_fence held-route row (the congress row is the free stack's).
FENCE_HELD = (*HELD, "congress_trades")


def _by(obs: list[A.Obs], series: str) -> dict[date, float]:
    return {o.period: o.value for o in obs if o.series == series}


# ============================================================================ terms
def test_pass5_rows_carry_their_terms_verdicts_and_verbatim_quotes() -> None:
    for sid in LIVE:
        assert A.BY_ID[sid].terms == "confirmed", sid
        ev = A.TERMS_EVIDENCE[sid]
        assert ev["terms_url"].startswith("https://") and len(ev["terms_quote"]) > 60, sid
        assert ev["checked_at"] == "2026-10-14", sid
    assert "commercial or noncommercial" in A.TERMS_EVIDENCE["us_usajobs_postings"]["terms_quote"]
    wiki = A.TERMS_EVIDENCE["wiki_asia_attention"]
    assert "User-Agent" in wiki["api_terms_quote"] and "contact" in wiki["ua_policy_quote"]


def test_each_hold_is_one_fence_row_with_a_quoted_clause_and_no_hosts() -> None:
    from libs.data import terms_fence as tf
    for sid in FENCE_HELD:
        row = tf.SOURCE_POLICY[sid]
        assert row["held_route"] is True and row["status"] == tf.IDEAS_ONLY, sid
        assert row["hosts"] == () and row["url_level"] is False, sid
        assert row["wanted"] and row["why"] and row["unblock"] and row["robots"], sid
        t = row["terms"]
        assert t["url"].startswith("https://") and t["checked_at"] == "2026-10-14", sid
        assert t["clauses"] and all(len(c) > 40 for c in t["clauses"].values()), sid
        assert tf.terms_state(sid) == "READ" and tf.held_on_terms(sid), sid
        assert sid in tf.HELD_ROUTE_KEYS and sid in A.HELD_ROUTES, sid
    for sid in tf.HELD_ROUTE_KEYS:                 # the queue rows too: the name finds the row
        assert tf.SOURCE_POLICY[sid]["sources"] == (sid,), sid
        assert tf.input_source(sid) == sid and tf.source_key(sid) == sid, sid
    q = {sid: " ".join(tf.SOURCE_POLICY[sid]["terms"]["clauses"].values()) for sid in FENCE_HELD}
    assert "non-commercial personal or professional use" in q["us_finra_regsho_short_volume"]
    assert "14 day trial" in q["gb_adzuna_vacancies"]
    assert "for any commercial purpose" in q["congress_trades"]


def test_no_second_register_for_the_holds() -> None:
    """The alt_proxies Source/TERMS rows and the roster's terms fields are gone: the fence row
    is the only record, and alt_proxies names the holds only through HELD_ROUTES."""
    for sid in HELD:
        assert sid not in A.BY_ID and sid not in A.TERMS and sid not in A.TERMS_EVIDENCE, sid
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "congress_trades")
    assert not {"terms", "terms_url", "terms_quote", "terms_judgement"} & set(row)


def test_held_rows_are_never_fetched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.request

    def _no_network(*a: Any, **k: Any) -> Any:
        raise AssertionError("network touched")
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, dry_run=True, now=NOW)
    for sid in HELD:
        assert sid not in rep["sources"] and rep["held_routes"][sid]["verdict"] == "HELD", sid
    assert not any("finra.org" in s.url or "adzuna" in s.url for s in A.SOURCES)


def test_alt_proxies_report_carries_a_missed_growth_line_per_hold(tmp_path: Path) -> None:
    rep = A.run(A.Paths(tmp_path / "desk"), fixtures=FIX, donate=False, dry_run=True, now=NOW)
    lines = {ln["source"]: ln for ln in rep["missed_growth_lines"]}
    assert set(lines) == set(A.HELD_ROUTES) >= set(FENCE_HELD)
    for sid in HELD:
        ln = lines[sid]
        assert ln["kind"] == "terms_hold" and ln["status"] == "HELD_ON_TERMS", sid
        assert ln["delta_elogw"] == "UNMEASURED", sid
        assert "no measured conversion on record" in ln["cause"], sid


def test_pass5_instruments_exist_and_no_crypto_exchange_host() -> None:
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for sid in (*LIVE, "wiki_asia_attention"):
        src = A.BY_ID[sid]
        for m in (src.instruments, *src.series_instruments.values()):
            assert set(m) <= set(uni), sid
        assert not any(x in src.url for x in ("binance", "bybit", "okx", "hyperliquid"))


# ============================================================================ F4 HKMA
def test_hkma_cu_flow_trigger_balance_and_hibor_parse_with_blanks_unmeasured() -> None:
    obs = A.parse_hkma_liquidity((FIX / "hk_hkma_liquidity.json").read_bytes(), A.Ctx())
    flow, trig = _by(obs, "hkma_cu_flow_mn"), _by(obs, "hkma_cu_trigger")
    assert flow[date(2026, 10, 7)] == -1250.0 and trig[date(2026, 10, 7)] == -1.0   # weak side
    assert flow[date(2026, 10, 6)] == -3800.0
    assert any(v == 620.0 for v in flow.values()) and 1.0 in trig.values()        # strong side
    assert set(trig.values()) <= {-1.0, 0.0, 1.0}
    n = 20
    assert len(_by(obs, "hkma_hibor_1m")) == n
    assert len(flow) == n - 1                       # the blank market_activities cell is absent
    assert len(_by(obs, "hkma_ab_close_mn")) == n - 1               # and so is the null balance
    assert A.parse_hkma_liquidity(b'{"result": {"records": "x"}}', A.Ctx()) == []


def test_hkma_requests_page_history_once_then_the_latest_rows() -> None:
    src = A.BY_ID["hk_hkma_liquidity"]
    first = A.requests_for(src, NOW, {})
    assert len(first) == 12 and "pagesize=1000&offset=0" in first[0].url
    assert "sortby=end_of_date&sortorder=desc" in first[0].url
    later = A.requests_for(src, NOW, {"full_done": True})
    assert len(later) == 1 and "pagesize=60&offset=0" in later[0].url


def test_hkma_signs_map_a_weak_side_drain_to_hk_equity_pressure() -> None:
    src = A.BY_ID["hk_hkma_liquidity"]
    # USDHKD follows the balance: a drain lifts HIBOR and pulls the pair off the weak side
    assert src.instruments_for("hkma_cu_flow_mn") == {"USDHKD": 1, "HK50": 1, "CHINAH": 1,
                                                      "USDCNH": -1}
    assert src.instruments_for("hkma_hibor_1m")["HK50"] == -1
    # PIT: the next HK business day, 12:00 UTC (the HKMA states no release hour: late-biased)
    assert src.rule(date(2026, 10, 9)) == datetime(2026, 10, 12, 12, tzinfo=UTC)
    assert "UNMEASURED" in src.note and "that Hong Kong evening" not in src.note


def test_hkma_stamp_rolls_past_hong_kong_holidays() -> None:
    src = A.BY_ID["hk_hkma_liquidity"]
    # Thu 2026-04-02 -> Good Friday 04-03, the weekend, Easter Monday 04-06 and Ching Ming
    # observed 04-07 are all shut: the first HK business day is Wed 04-08
    assert src.rule(date(2026, 4, 2)) == datetime(2026, 4, 8, 12, tzinfo=UTC)
    # Thu 2026-12-24 -> Christmas Fri 12-25, Boxing Day falls on the Saturday: Mon 12-28
    assert src.rule(date(2026, 12, 24)) == datetime(2026, 12, 28, 12, tzinfo=UTC)
    # Lunar New Year 2026 (02-17..19): Mon 02-16 -> Fri 02-20
    assert src.rule(date(2026, 2, 16)) == datetime(2026, 2, 20, 12, tzinfo=UTC)
    assert src.rule_basis is not None
    assert src.rule_basis(date(2026, 4, 2)).startswith("hk_business_day")
    # a year the HK table does not cover: three EXTRA weekdays, plus one for the untabled
    # pre-2024-09-23 typhoon closures, and the basis names both
    assert A.hk_general_holidays(2019) is None
    assert src.rule(date(2019, 3, 7)) == datetime(2019, 3, 14, 12, tzinfo=UTC)   # Fri +3 +1
    assert "late_bias:+3 HK weekdays" in src.rule_basis(date(2019, 3, 7))
    assert "typhoon" in src.rule_basis(date(2019, 3, 7))
    for d in (date(2024, 3, 28), date(2025, 12, 24), date(2026, 9, 30)):
        assert src.rule(d).date() not in (A.hk_general_holidays(src.rule(d).year) or ()), d
        assert src.rule(d).weekday() < 5, d


def test_hkma_store_rows_record_their_rule_basis() -> None:
    src = A.BY_ID["hk_hkma_liquidity"]
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, [A.Obs("hkma_cu_flow_mn", date(2026, 4, 2), -1.0),
                                  A.Obs("hkma_cu_flow_mn", date(2019, 3, 7), 2.0)], NOW)
    assert store["hkma_cu_flow_mn|2026-04-02"]["published_time"].startswith("2026-04-08T12")
    assert store["hkma_cu_flow_mn|2026-04-02"]["rule_basis"].startswith("hk_business_day")
    assert "late_bias:+3" in store["hkma_cu_flow_mn|2019-03-07"]["rule_basis"]


# ============================================================================ GAP1 USAJOBS
def test_usajobs_needs_key_and_email_and_carries_them_only_in_headers(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = A.BY_ID["us_usajobs_postings"]
    monkeypatch.delenv("USAJOBS_API_KEY", raising=False)
    monkeypatch.delenv("USAJOBS_USER_AGENT", raising=False)
    assert A.status_of(src) == "BLOCKED_ON_KEY:USAJOBS_API_KEY"
    assert A.requests_for(src, NOW, {}) == []
    secret, mail = "k3y-not-real-0001", "desk@example.invalid"
    monkeypatch.setenv("USAJOBS_API_KEY", secret)
    assert A.status_of(src) == "UNCONFIGURED:USAJOBS_USER_AGENT"
    assert A.requests_for(src, NOW, {}) == []
    monkeypatch.setenv("USAJOBS_USER_AGENT", mail)
    reqs = A.requests_for(src, NOW, {})
    assert [r.ctx.part for r in reqs] == [p for p, _ in A.USAJOBS_CUTS]
    for r in reqs:
        assert secret not in r.url and mail not in r.url
        assert r.headers == {"Host": "data.usajobs.gov", "User-Agent": mail,
                             "Authorization-Key": secret}
    seen: list[tuple[str, dict[str, str]]] = []

    def getter(url: str, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
        seen.append((url, dict(headers or {})))
        return (FIX / "us_usajobs_postings.json").read_bytes(), "application/json"

    paths = A.Paths(tmp_path / "desk")
    rec = A.collect(paths, src, {}, NOW, fetch=True, fixtures=None, deadline=1e18, getter=getter)
    assert len(seen) == len(A.USAJOBS_CUTS) and rec["parsed"] == len(A.USAJOBS_CUTS)
    for meta in (paths.vault / "alt_us_usajobs_postings").glob("*.meta.json"):
        text = meta.read_text("utf-8")
        assert secret not in text and mail not in text


def test_usajobs_count_is_first_seen_pit() -> None:
    at = datetime(2026, 10, 14, 7, 5, tzinfo=UTC)
    obs = A.parse_usajobs_count((FIX / "us_usajobs_postings.json").read_bytes(),
                                A.Ctx(part="new_1d", fetched_at=at))
    assert obs == [A.Obs("usajobs_new_1d", date(2026, 10, 14), 4321.0, published_at=at)]
    store: dict[str, Any] = {}
    A.merge_vintages(store, A.BY_ID["us_usajobs_postings"], obs, at)
    row = store["usajobs_new_1d|2026-10-14"]
    assert row["published_time"] == at.isoformat(timespec="seconds")      # the fetch instant
    assert row["published_basis"] == "page"
    assert A.parse_usajobs_count(b'{"SearchResult": {}}', A.Ctx()) == []    # absent, not zero


# ============================================================================ N6 wiki
def test_wiki_reads_the_new_currency_articles_with_the_policy_user_agent() -> None:
    src = A.BY_ID["wiki_asia_attention"]
    labels = [lb for lb, _p, _t in A.WIKI_ASIA_ARTICLES]
    for lb in ("ja_yen", "tr_lira", "es_mxn", "pt_brl", "ko_krw", "ko_jpy"):
        assert lb in labels
    reqs = A.requests_for(src, NOW, {"full_done": True})
    by = {r.ctx.part: r for r in reqs}
    # a state that read the seven legacy articles in full reads them by window; every new
    # article gets its own full history once
    assert "/20260830/" in by["ja_boj"].url and "/20150701/" in by["tr_lira"].url
    assert "/tr.wikipedia/all-access/user/T%C3%BCrk_liras%C4%B1/" in by["tr_lira"].url
    assert "Real_%28moeda_brasileira%29" in by["pt_brl"].url        # spaces as underscores
    for r in reqs:
        ua = r.headers["User-Agent"]
        assert ua.startswith("quant-desk-alt-proxies/") and "(" in ua and "http" in ua
        assert "Mozilla" not in ua
    done = A.requests_for(src, NOW, {"full_done": True, "full_labels": labels})
    assert all("/20150701/" not in r.url for r in done)


def test_wiki_full_history_is_marked_read_only_for_articles_that_answered(
        tmp_path: Path) -> None:
    src = A.BY_ID["wiki_asia_attention"]
    body = (FIX / "wiki_asia_attention.json").read_bytes()

    def getter(url: str, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
        if "Peso_mexicano" in url:
            raise OSError("404 Not Found")
        return body, "application/json"

    state: dict[str, Any] = {}
    A.collect(A.Paths(tmp_path / "desk"), src, state, NOW, fetch=True, fixtures=None,
              deadline=1e18, getter=getter)
    sst = state["sources"]["wiki_asia_attention"]
    assert "es_mxn" not in sst["full_labels"] and "tr_lira" in sst["full_labels"]
    assert "full_done" not in sst                     # an error pass commits no window flag
    again = {r.ctx.part: r for r in A.requests_for(src, NOW, sst)}
    assert "/20150701/" in again["es_mxn"].url and "/20150701/" not in again["tr_lira"].url


def test_wiki_currency_labels_map_before_the_language_prefixes() -> None:
    src = A.BY_ID["wiki_asia_attention"]
    assert src.instruments_for("ko_jpy_views") == {"USDJPY": -1}
    assert src.instruments_for("ko_krw_views") == {"USDKRW": 1}
    assert src.instruments_for("tr_crisis_views") == {"USDTRY": -1}
    assert src.instruments_for("pt_brl_views") == {"USDBRL": -1}
    assert src.instruments_for("es_mxn_views") == {"USDMXN": -1}
    assert src.instruments_for("ja_yen_rate_views") == {"USDJPY": -1}


def test_fixture_pass_publishes_the_hkma_axis(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    assert rep["sources"]["hk_hkma_liquidity"]["series"]["hkma_cu_flow_mn"] == 19
    doc = json.loads((paths.axes / "alt_hk_hkma_liquidity.json").read_text("utf-8"))
    assert doc["series"]
    for sid in HELD:
        assert sid in rep["held_routes"]


# ============================================================================ GAP2 congress
_PTR = json.dumps([
    {"disclosure_date": "09/21/2026", "transaction_date": "2026-08-30", "ticker": "NVDA",
     "type": "purchase", "amount": "$1,001 - $15,000", "representative": "Hon. X",
     "owner": "spouse"},
    {"disclosure_date": "09/21/2026", "transaction_date": "2026-08-29", "ticker": "AAPL",
     "type": "sale_full", "amount": "$15,001 - $50,000"},
    {"disclosure_date": "09/22/2026", "transaction_date": "2026-09-01", "ticker": "MSFT",
     "type": "sale_partial", "amount": "Over $50,000,000"},
    {"disclosure_date": "09/22/2026", "transaction_date": "2026-09-01", "ticker": "--",
     "type": "purchase", "amount": "$1,001 - $15,000"},
    {"disclosure_date": "09/22/2026", "transaction_date": "2026-09-01", "ticker": "IBM",
     "type": "exchange", "amount": "$1,001 - $15,000"},
    {"disclosure_date": "09/22/2026", "transaction_date": "2026-09-02", "ticker": "AMD",
     "type": "purchase", "amount": "unknown"},
]).encode()


def test_ptr_trades_keep_the_trade_and_drop_the_person() -> None:
    trades = fs.parse_ptr_trades(_PTR)
    assert [t["ticker"] for t in trades] == ["NVDA", "AAPL", "MSFT"]
    nv = trades[0]
    assert nv == {"ticker": "NVDA", "side": 1, "band_lo": 1001.0, "band_hi": 15000.0,
                  "transaction_date": "2026-08-30", "filing_date": "2026-09-21",
                  "filing_lag_d": 22}
    assert trades[2]["band_hi"] is None and trades[2]["side"] == -1          # open top band
    assert not any("representative" in t or "owner" in t for t in trades)


def test_ptr_trade_series_are_filing_dated_and_single_names_event_only() -> None:
    obs, cols = fs.ptr_trade_obs(fs.parse_ptr_trades(_PTR))
    v = {(o["key"], o["period_end"]): o["value"] for o in obs}
    assert v[("ptr_net_usd_mid", "2026-09-21")] == pytest.approx(8000.5 - 32500.5)
    assert v[("ptr_net_usd_mid", "2026-09-22")] == pytest.approx(-50_000_000.0)
    assert v[("ptr_trades", "2026-09-21")] == 2
    assert all(o["period_end"] >= "2026-09-21" for o in obs)      # never the transaction date
    for k, meta in cols.items():
        if k.startswith("ptrusd_"):
            assert meta["hypothesis"] == [] and meta["event"], k


def _congress_pass(tmp_path: Path, cursor: dict[str, Any] | None = None) -> dict[str, Any]:
    from free_stack_hunter import Store, run
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "congress_trades")
    tmp_path.mkdir(parents=True, exist_ok=True)
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"sources": [row]}), "utf-8")
    store = Store(tmp_path)
    if cursor is not None:
        store.cursor.parent.mkdir(parents=True, exist_ok=True)
        store.cursor.write_text(json.dumps(cursor), "utf-8")
    return run(budget_s=30, fetch=lambda *a: (_ for _ in ()).throw(AssertionError("fetched")),
               store=store, roster=roster, now=NOW, live=False)


def test_congress_row_is_held_because_of_its_fence_row(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.data import terms_fence as tf
    rep = _congress_pass(tmp_path / "a")
    per = rep["per_source"]["congress_trades"]
    assert per["status"] == "HELD_ON_TERMS" and "commercial purpose" in per["last_error"]
    assert "terms_fence congress_trades" in per["last_error"]
    # the hold IS the fence row: lift the row and the hunter no longer holds on terms
    monkeypatch.setitem(tf.SOURCE_POLICY, "congress_trades",
                        {**tf.SOURCE_POLICY["congress_trades"], "held_route": False,
                         "status": tf.PUBLIC_PAGE})
    assert not tf.held_on_terms("congress_trades")
    rep2 = _congress_pass(tmp_path / "b")
    assert rep2["per_source"]["congress_trades"]["status"] != "HELD_ON_TERMS"


def test_congress_hold_carries_its_missed_growth_line(tmp_path: Path) -> None:
    rep = _congress_pass(tmp_path / "a")
    ln = next(x for x in rep["missed_growth_lines"] if x["source"] == "congress_trades")
    assert ln["kind"] == "terms_hold" and ln["status"] == "HELD_ON_TERMS"
    assert ln["delta_elogw"] == "UNMEASURED"
    assert "no measured conversion on record" in ln["cause"] and "past_conversion" not in ln
    # a fetch that USED to run: the organ's own pre-hold record is carried as past conversion
    rep = _congress_pass(tmp_path / "b", {"congress_trades": {
        "attempts": 9, "successes": 4, "obs_total": 120, "last_success": "2026-10-01T00:00:00Z"}})
    ln = next(x for x in rep["missed_growth_lines"] if x["source"] == "congress_trades")
    assert ln["past_conversion"] == {"attempts": 9, "successes": 4, "obs_total": 120,
                                     "last_success": "2026-10-01T00:00:00Z"}
    assert ln["delta_elogw"] == "UNMEASURED"


# ============================================================================ GAP3 deep forest
_ROBOTS = "User-agent: *\nDisallow: /private/\nSitemap: https://ex.example/sitemap.xml\n"
_SITEMAP = ("<urlset><url><loc>https://ex.example/forum/thread-1.html</loc></url>"
            "<url><loc>https://ex.example/private/x.html</loc></url>"
            "<url><loc>https://ex.example/logo.png</loc></url>"
            "<url><loc>https://other.example/a.html</loc></url></urlset>")


def test_site_index_prefers_the_sitemap_and_honours_robots() -> None:
    calls: list[str] = []

    def get(url: str) -> str:
        calls.append(url)
        return {"https://ex.example/robots.txt": _ROBOTS,
                "https://ex.example/sitemap.xml": _SITEMAP}[url]
    out = D.site_index_urls("ex.example", get=get)
    assert out["route"] == "sitemap"
    assert out["urls"] == ["https://ex.example/forum/thread-1.html"]
    assert out["robots_disallowed"] == 1 and out["listed"] == 2
    assert not any("commoncrawl" in c for c in calls)


def test_site_index_falls_back_to_the_common_crawl_cdx() -> None:
    cdx = "\n".join(json.dumps({"url": u}) for u in (
        "https://ex.example/a/strategy-notes.html", "https://ex.example/private/b.html"))

    def get(url: str) -> str:
        if url.endswith("robots.txt"):
            return "User-agent: *\nDisallow: /private/\n"
        assert url.startswith("https://index.commoncrawl.org/") and "ex.example%2F%2A" in url
        return cdx
    out = D.site_index_urls("ex.example", get=get)
    assert out["route"] == "cdx" and out["urls"] == ["https://ex.example/a/strategy-notes.html"]


def test_unread_robots_fetches_nothing() -> None:
    def get(url: str) -> str:
        if url.endswith("robots.txt"):
            raise OSError("HTTP 403")
        return json.dumps({"url": "https://ex.example/a.html"})
    out = D.site_index_urls("ex.example", get=get)
    assert out["urls"] == [] and out["listed"] == 1
    assert any("robots.txt unread" in e for e in out["errors"])


def test_the_bing_block_is_rerouted_not_bypassed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(D, "engine_search", lambda *a, **k: ([], "", ["bing: anti-bot"]))
    seen: list[str] = []
    monkeypatch.setattr(D, "site_index_urls", lambda site, **k: seen.append(site) or {
        "route": "cdx", "urls": [], "listed": 0, "robots_disallowed": 0, "errors": []})
    r = D._Run(60.0, True, None, None)
    out = r.ground_search({"name": "g", "site": "ex.example", "queries": ["q1"],
                           "language": "en"})
    assert seen == ["ex.example"] and out["index_route"]["route"] == "cdx"
    assert "bing" not in json.dumps(out["index_route"])
    src = Path(D.__file__).read_text("utf-8")
    seg = src[src.index("def site_index_urls"):src.index("def bing_reroute_census")]
    assert "Mozilla" not in seg and "_UA" not in seg          # the honest agent only


def test_bing_reroute_census_counts_rerouted_and_blocked_with_cause() -> None:
    grounds = [{"name": "a", "route": "search", "site": "a.example"},
               {"name": "b", "route": "search"},
               {"name": "c", "route": "youtube"},
               {"name": "d", "route": "http", "url": "https://d.example"}]
    vectors = {"a": {"outcome": "BLOCKED"}, "b": {"outcome": "BLOCKED"},
               "d": {"outcome": "BLOCKED"}, "x": {"outcome": "YIELDED"}}
    c = D.bing_reroute_census(grounds, vectors)
    assert c["bing_dependent_grounds"] == 3 and c["rerouted"] == 1
    assert set(c["still_blocked"]) == {"b", "c"}
    assert c["frontier_blocked_vectors"] == 3 and c["frontier_blocked_bing_dependent"] == 2
    assert c["frontier_blocked_rerouted"] == 1 and set(c["frontier_blocked_other_cause"]) == {"d"}
    real = json.loads((DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    rc = D.bing_reroute_census(real["grounds"])
    assert rc["rerouted"] + len(rc["still_blocked"]) == rc["bing_dependent_grounds"]


# ============================================================================ audit 2026-10-14
def test_usajobs_host_header_follows_the_request_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace
    from urllib.parse import urlparse
    monkeypatch.setenv("USAJOBS_API_KEY", "k3y-not-real-0002")
    monkeypatch.setenv("USAJOBS_USER_AGENT", "desk@example.invalid")
    src = replace(A.BY_ID["us_usajobs_postings"], url="https://mirror.example.invalid/api/search")
    for r in A.requests_for(src, NOW, {}):
        assert r.headers["Host"] == urlparse(r.url).netloc == "mirror.example.invalid"


def test_ideas_only_row_still_mined_and_labelled_not_held(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditor ruling: IDEAS_ONLY still mines ideas. The free-stack telegram row is not held on
    terms (it reaches run_source and is labelled IDEAS_ONLY, carrying no terms-hold line), and a
    telegram idea ground in the deep forest is still fetched."""
    from libs.data import terms_fence as tf
    assert tf.SOURCE_POLICY["telegram"]["status"] == tf.IDEAS_ONLY
    assert not tf.held_on_terms("telegram") and tf.fenced_ground(
        {"route": "telegram", "channels": ["x"]}) is None
    from free_stack_hunter import Store, run
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "telegram")
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"sources": [row]}), "utf-8")
    rep = run(budget_s=30, fetch=lambda *a: (_ for _ in ()).throw(AssertionError("fetched")),
              store=Store(tmp_path), roster=roster, now=NOW, live=False)
    assert rep["per_source"]["telegram"]["status"] == tf.IDEAS_ONLY
    # the live-input refusal carries its missed-growth line (IDEAS_ONLY, not a terms hold)
    (ln,) = [x for x in rep["missed_growth_lines"] if x["source"] == "telegram"]
    assert ln["kind"] == "ideas_only_refusal" and ln["status"] == tf.IDEAS_ONLY
    assert ln["delta_elogw"] == "UNMEASURED" and "ideas still mined" in ln["cause"]
    # the idea route: a deep-forest telegram ground fetches its public previews
    asked: list[str] = []

    def http(url: str, **k: Any) -> str:
        asked.append(url)
        return "<html><body>" + "gold breakout rule. " * 40 + "</body></html>"
    monkeypatch.setattr(D, "_http", http)
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    r = D._Run(60.0, True, None, None)
    r.ground_telegram({"name": "t", "route": "telegram", "channels": ["chan_a"],
                       "language": "ru", "kind": "social"})
    assert "https://t.me/s/chan_a" in asked


def test_rerouted_pages_are_fetched_with_the_index_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    sent: list[tuple[str, dict[str, str]]] = []

    def get(url: str, headers: dict[str, str] | None = None, **k: Any) -> Any:
        sent.append((url, dict(headers or {})))
        return SimpleNamespace(ok=True, status=200, error=None,
                               text="<html><title>t</title><body>" + "rule. " * 600
                                    + "</body></html>")
    monkeypatch.setattr(D.pf, "get", get)
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    monkeypatch.setattr(D, "site_index_urls", lambda site, **k: {
        "route": "sitemap", "urls": ["https://ex.example/forum/a.html"], "listed": 1,
        "robots_disallowed": 0, "robots_unread": 0, "errors": []})
    r = D._Run(60.0, True, None, None)
    out = r.ground_site_index({"name": "g", "site": "ex.example", "queries": ["rule"],
                               "language": "en"})
    pages = [(u, h) for u, h in sent if u == "https://ex.example/forum/a.html"]
    assert out["fetched"] == 1 and pages
    for _, h in pages:
        assert h["User-Agent"] == D.INDEX_UA
        # one honest constant serves every route: never a browser string
        assert h["User-Agent"] == D._UA["User-Agent"] and "Mozilla" not in h["User-Agent"]


def test_a_subdomain_page_needs_its_own_hosts_robots() -> None:
    sm = ("<urlset><url><loc>https://m.ex.com/ok/y</loc></url>"
          "<url><loc>https://ex.com/ok/x</loc></url></urlset>")
    parent = "User-agent: *\nAllow: /\nSitemap: https://ex.com/sitemap.xml\n"

    def make(sub: str | None) -> Any:
        def get(url: str) -> str:
            if url == "https://ex.com/robots.txt":
                return parent
            if url == "https://ex.com/sitemap.xml":
                return sm
            if url == "https://m.ex.com/robots.txt" and sub is not None:
                return sub
            raise OSError("HTTP 404")
        return get
    # m.ex.com's own robots.txt unread: the parent's Allow is NOT a permission for it
    out = D.site_index_urls("ex.com", get=make(None))
    assert out["urls"] == ["https://ex.com/ok/x"] and out["robots_unread"] == 1
    # read and allowing: fetched
    out = D.site_index_urls("ex.com", get=make("User-agent: *\nAllow: /\n"))
    assert "https://m.ex.com/ok/y" in out["urls"]
    # read and disallowing, though the parent allows: never fetched
    out = D.site_index_urls("ex.com", get=make("User-agent: *\nDisallow: /ok/\n"))
    assert "https://m.ex.com/ok/y" not in out["urls"] and out["robots_disallowed"] == 1


def test_tga_stamp_rolls_past_one_off_federal_closures() -> None:
    """Auditor should-fix (gd-queue-rows, folded here): executive-order closures are a dated set
    unioned into the business-day roll; late-biased, never early."""
    body = json.dumps({"data": [{"record_date": "2025-01-08", "account_type":
                                 "Treasury General Account (TGA) Closing Balance",
                                 "close_today_bal": "null", "open_today_bal": "800000"}]})
    (o,) = A.parse_net_liquidity(body.encode(), A.Ctx())
    assert o.published_at == datetime(2025, 1, 10, 22, tzinfo=UTC)         # not 01-09
    assert A.rule_net_liquidity(date(2025, 1, 8)) == datetime(2025, 1, 10, 22, tzinfo=UTC)
    closures = {date(2024, 12, 24), date(2025, 1, 9), date(2025, 12, 24), date(2025, 12, 26)}
    assert set(A.US_FEDERAL_CLOSURES) == closures
    assert A.rule_net_liquidity(date(2024, 12, 23)) == datetime(2024, 12, 26, 22, tzinfo=UTC)
    assert A.rule_net_liquidity(date(2025, 12, 23)) == datetime(2025, 12, 29, 22, tzinfo=UTC)


# ============================================================================ audit 1da3e0a8a
@pytest.mark.parametrize(("period", "true_next"), [
    (date(2019, 2, 4), date(2019, 2, 8)),       # Lunar New Year 2019-02-05..07
    (date(2023, 1, 20), date(2023, 1, 26)),     # Lunar New Year 2023-01-23..25
    (date(2015, 4, 2), date(2015, 4, 8)),       # Good Friday, Easter Monday, Ching Ming 04-07
    (date(2027, 2, 5), date(2027, 2, 10)),      # Lunar New Year 2027-02-08..09 (untabled year)
])
def test_hkma_stamp_is_never_early_in_an_untabled_year(period: date, true_next: date) -> None:
    src = A.BY_ID["hk_hkma_liquidity"]
    assert A.hk_general_holidays(period.year) is None
    t = src.rule(period)
    assert t >= datetime(true_next.year, true_next.month, true_next.day, 12, tzinfo=UTC), period
    assert t.weekday() < 5
    assert src.rule_basis is not None and "late_bias:+3" in src.rule_basis(period)


def test_hkma_severe_weather_bias_before_2024_09_23() -> None:
    src = A.BY_ID["hk_hkma_liquidity"]
    assert src.rule_basis is not None
    # tabled year, before the 2024-09-23 rule change: one more business day for typhoon closures
    assert src.rule(date(2024, 9, 5)) == datetime(2024, 9, 9, 12, tzinfo=UTC)    # Thu -> Mon
    assert "typhoon" in src.rule_basis(date(2024, 9, 5))
    # after it: the plain next business day
    assert src.rule(date(2024, 10, 3)) == datetime(2024, 10, 4, 12, tzinfo=UTC)
    assert "late_bias" not in src.rule_basis(date(2024, 10, 3))


def test_index_route_urls_never_reach_the_frontier(monkeypatch: pytest.MonkeyPatch) -> None:
    """MF-B: the frontier is fetched by world_crawler.fetch (browser agent, no robots check), so a
    page the index route read is never followed into it."""
    from types import SimpleNamespace
    url = "https://ex.example/forum/a.html"
    monkeypatch.setattr(D.pf, "get", lambda *a, **k: SimpleNamespace(
        ok=True, status=200, error=None,
        text="<html><title>t</title><body>" + "rule. " * 600 + "</body></html>"))
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    monkeypatch.setattr(D, "site_index_urls", lambda site, **k: {
        "route": "sitemap", "urls": [url], "listed": 1, "robots_disallowed": 0,
        "robots_unread": 0, "errors": []})
    r = D._Run(60.0, True, None, None)
    out = r.ground_site_index({"name": "g", "site": "ex.example", "queries": ["rule"],
                               "language": "en"})
    assert out["fetched"] == 1
    assert url not in [u for u, _, _ in r.frontier] and url in r.seen_urls
    # and nothing of it is handed to the crawler's frontier store
    added: list[str] = []
    fake = SimpleNamespace(load=lambda: {}, save=lambda *a, **k: None,
                           add=lambda src, u, **k: added.append(u) or True)
    monkeypatch.setitem(sys.modules, "world_frontier", fake)
    D._feed_frontier(list(r.frontier))
    assert url not in added


def test_robots_origin_includes_a_non_default_port() -> None:
    assert D.robots_origin("https://ex.com/a") == "https://ex.com"
    assert D.robots_origin("https://ex.com:443/a") == "https://ex.com"
    assert D.robots_origin("https://ex.com:8443/a") == "https://ex.com:8443"
    assert D.robots_origin("http://ex.com/a") == "http://ex.com"
    sm = "<urlset><url><loc>https://ex.com:8443/ok/p</loc></url></urlset>"

    def get(url: str) -> str:
        return {"https://ex.com/robots.txt":
                "User-agent: *\nAllow: /\nSitemap: https://ex.com/sitemap.xml\n",
                "https://ex.com/sitemap.xml": sm}[url]     # port 8443's robots.txt: unreadable
    out = D.site_index_urls("ex.com", get=get)
    assert out["urls"] == [] and out["robots_unread"] == 1
    reads: list[str] = []

    def get2(url: str) -> str:
        reads.append(url)
        if url == "https://ex.com:8443/robots.txt":
            return "User-agent: *\nAllow: /\n"
        return get(url)
    out = D.site_index_urls("ex.com", get=get2)
    assert out["urls"] == ["https://ex.com:8443/ok/p"]
    assert "https://ex.com:8443/robots.txt" in reads


def test_a_cross_origin_redirect_needs_the_new_origins_robots() -> None:
    import io
    import urllib.error
    import urllib.request

    def handler(allow: bool) -> Any:
        h = D.IndexRedirectHandler(lambda u: allow)
        h.parent = urllib.request.build_opener()
        return h
    req = urllib.request.Request("https://ex.com/a", headers={"User-Agent": D.INDEX_UA})
    # another origin, its robots.txt unread or disallowing: stopped at the 30x
    with pytest.raises(urllib.error.HTTPError) as e:
        handler(False).redirect_request(req, io.BytesIO(b""), 301, "Moved", {},
                                        "https://other.example/b")
    assert "cross-origin redirect stopped" in str(e.value.reason)
    with pytest.raises(urllib.error.HTTPError):                 # another port is another origin
        handler(False).redirect_request(req, io.BytesIO(b""), 302, "Found", {},
                                        "https://ex.com:8443/b")
    # allowed by the new origin's own robots.txt, or the same origin: followed
    new = handler(True).redirect_request(req, io.BytesIO(b""), 301, "Moved", {},
                                         "https://other.example/b")
    assert new is not None and new.full_url == "https://other.example/b"
    same = handler(False).redirect_request(req, io.BytesIO(b""), 301, "Moved", {},
                                           "https://ex.com/c")
    assert same is not None and same.full_url == "https://ex.com/c"
    # robots_allows reads the target ORIGIN's own file, and an unread one is not a permission
    asked: list[str] = []

    def get(url: str) -> str:
        asked.append(url)
        raise OSError("HTTP 404")
    assert D.robots_allows("https://other.example:8080/b", get=get) is False
    assert asked == ["https://other.example:8080/robots.txt"]


# ============================================================================ audit c237d8848
# MF-B (second path): a page the index route read, its dataset() row and the endpoints on it never
# reach the world_crawler frontier; the discovery row is tagged for INDEX_UA + robots.txt.
# MF-C: the first 401/403/429 holds the site for the run (persisted as the ground's frontier
# vector), no CDX fallback for a held site, and a 429 is never retried.
def _index_run(monkeypatch: pytest.MonkeyPatch, body: str, kind: str = "forum",
               get: Any = None) -> tuple[str, Any, dict[str, Any]]:
    from types import SimpleNamespace
    url = "https://ex.example/data/page.html"
    monkeypatch.setattr(D.pf, "get", get or (lambda *a, **k: SimpleNamespace(
        ok=True, status=200, error=None, text=body)))
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    monkeypatch.setattr(D, "site_index_urls", lambda site, **k: {
        "route": "sitemap", "urls": [url], "listed": 1, "robots_disallowed": 0,
        "robots_unread": 0, "errors": []})
    r = D._Run(60.0, True, None, None)
    out = r.ground_site_index({"name": "g", "site": "ex.example", "queries": ["rule"],
                               "language": "en", "kind": kind})
    return url, r, out


def test_an_index_page_with_a_csv_link_leaves_nothing_in_the_frontier(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = ("<html><title>t</title><body>" + "rule. " * 600 +
            '<a href="/files/prices.csv">csv</a>'
            '<a href="https://ex.example/api/v1/series?x=1">api</a></body></html>')
    url, r, out = _index_run(monkeypatch, body)
    assert out["fetched"] == 1 and r.frontier == []
    assert url in r.seen_urls
    (row,) = r.datasets
    assert row["n_endpoints"] >= 1 and row["route"] == "index"
    assert row["fetch_policy"]["user_agent"] == D.INDEX_UA
    assert row["fetch_policy"]["robots_txt"] == "required"


def test_a_dataset_kind_ground_on_the_index_route_leaves_nothing_in_the_frontier(
        monkeypatch: pytest.MonkeyPatch) -> None:
    body = "<html><title>t</title><body>" + "rule. " * 600 + "</body></html>"
    _url, r, out = _index_run(monkeypatch, body, kind="dataset")
    assert out["fetched"] == 1 and r.frontier == []
    (row,) = r.datasets
    assert row["route"] == "index"


def test_a_non_index_dataset_page_is_still_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fix is scoped to the index route: the http route's dataset page keeps its follow."""
    r = D._Run(60.0, True, None, None)
    page = '<a href="/files/prices.csv">csv</a>'
    r.dataset(page, ground={"name": "g", "kind": "dataset"},
              url="https://ex.example/d.html", title="t", route="http")
    assert [u for u, _, _ in r.frontier] == ["https://ex.example/d.html"]
    assert "route" not in r.datasets[0]


def test_the_acquirer_never_selects_an_index_route_endpoint(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import acquire_datasets as acq
    world = tmp_path / "world"
    world.mkdir()
    (world / "discoveries_deepforest_20261014_0000.json").write_text(json.dumps([
        {"kind": "dataset", "route": "index", "host": "ex.example",
         "endpoints": ["https://ex.example/files/index-only.csv"]},
        {"kind": "dataset", "host": "ok.example",
         "endpoints": ["https://ok.example/files/plain.csv"]}]), "utf-8")
    monkeypatch.setattr(acq, "WORLD", world)
    monkeypatch.setattr(acq, "REGISTRY", tmp_path / "missing.json")
    picked = [u for u, _ in acq._endpoints(10 ** 6, now=NOW)]
    assert "https://ex.example/files/index-only.csv" not in picked
    assert "https://ok.example/files/plain.csv" in picked
    assert acq._ENDPOINT_FENCED.get(acq.INDEX_ROUTE_SKIP) == 1


@pytest.mark.parametrize("code", [401, 403, 429])
def test_one_refusal_stops_every_request_to_that_host(monkeypatch: pytest.MonkeyPatch,
                                                      code: int) -> None:
    from types import SimpleNamespace
    calls: list[tuple[str, int]] = []

    def get(url: str, **k: Any) -> Any:
        calls.append((url, int(k.get("retries", -1))))
        return SimpleNamespace(ok=False, status=code, error=f"HTTP {code}", text="")
    monkeypatch.setattr(D.pf, "get", get)
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    urls = [f"https://ex.example/rule/p{i}.html" for i in range(6)]
    monkeypatch.setattr(D, "site_index_urls", lambda site, **k: {
        "route": "sitemap", "urls": urls, "listed": 6, "robots_disallowed": 0,
        "robots_unread": 0, "errors": []})
    r = D._Run(60.0, True, None, None)
    g = {"name": "g", "site": "ex.example", "queries": ["rule"], "language": "en"}
    r.ground_site_index(g)
    assert len(calls) == 1 and calls[0][1] == 0                   # one request, no retry
    assert (r.holds.held("www.ex.example") or {}).get("status") == code   # the whole site
    # every other route of the run is held too: no request, recorded as held
    assert r.page("https://sub.ex.example/x") == "" and len(calls) == 1
    assert r.ground_site_index(g)["route"] == "held" and len(calls) == 1


def test_a_sitemap_429_means_no_cdx_and_no_page(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    calls: list[str] = []

    def get(url: str, **k: Any) -> Any:
        calls.append(url)
        assert k.get("retries") == 0                              # a 429 is never retried
        if url.endswith("robots.txt"):
            return SimpleNamespace(ok=True, status=200, error=None,
                                   text="User-agent: *\nAllow: /\n"
                                        "Sitemap: https://ex.example/sitemap.xml\n")
        if url.endswith("sitemap.xml"):
            return SimpleNamespace(ok=False, status=429, error="HTTP 429", text="")
        raise AssertionError(f"requested after the 429: {url}")
    monkeypatch.setattr(D.pf, "get", get)
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    r = D._Run(60.0, True, None, None)
    out = r.ground_site_index({"name": "g", "site": "ex.example", "queries": ["rule"],
                               "language": "en"})
    assert out["route"] == "held" and out["fetched"] == 0
    assert calls == ["https://ex.example/robots.txt", "https://ex.example/sitemap.xml"]
    assert not any("commoncrawl" in c for c in calls)
    # the module function alone, with a plain getter: the same stop
    seen: list[str] = []

    def raw(url: str) -> str:
        seen.append(url)
        if url.endswith("robots.txt"):
            return "User-agent: *\nSitemap: https://ex.example/sitemap.xml\n"
        raise D.SiteRefused(url, 403)
    got = D.site_index_urls("ex.example", get=raw)
    assert got["route"] == "held" and got["urls"] == []
    assert not any("commoncrawl" in u for u in seen)


def test_the_index_route_never_asks_polite_fetch_to_retry() -> None:
    src = Path(D.__file__).read_text("utf-8")
    for fn in ("def _index_get", "def index_page"):
        seg = src[src.index(fn):src.index(fn) + 1500]
        assert "retries=0" in seg and "retries=1" not in seg, fn


def test_a_site_hold_is_persisted_in_the_frontier_and_reseeded(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import hunt_frontier as hf
    monkeypatch.setattr(D, "_frontier_path", lambda: tmp_path / "frontier.json")
    g = {"name": "g", "site": "ex.example", "language": "en", "region": "x"}
    D._record_frontier([{"ground": "g", "status": D.ACCESS_REFUSED, "language": "en",
                         "why": "HTTP 403 from ex.example: site held for the run"}], [g])
    state = hf.load(tmp_path / "frontier.json")
    v = state.vectors["g"]
    assert v.outcome == "BLOCKED" and v.blocker.startswith(D.ACCESS_REFUSED)
    held = D.persisted_site_holds([g], state)
    assert set(held) == {"ex.example"}
    # past the hunt_frontier retry clock the hold does NOT lift: it waits for a person
    later = datetime.now(tz=UTC).replace(year=datetime.now(tz=UTC).year + 1)
    assert set(D.persisted_site_holds([g], state, now=later)) == {"ex.example"}
    # a ground on a held site is skipped with a missed-growth line, and SITE_HELD never
    # refreshes the frontier stamp (it is not a frontier outcome)
    r = D._Run(60.0, True, None, None)
    r.holds.hold("https://ex.example/", 403, persisted=True)
    r.work({**g, "route": "http", "url": "https://www.ex.example/a"})
    (row,) = [s for s in r.status if s.get("ground") == "g"]
    assert row["status"] == "SITE_HELD"
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert "SITE_HELD" not in D._FRONTIER_OUTCOME


def test_a_refusal_older_than_the_retry_clock_still_blocks_every_request(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditor ruling 2026-10-14: a 401/403/429 hold waits for a PERSON. A hold 30 days old
    (three times hunt_frontier's 10-day BLOCKED retry) still blocks every request, the BLOCKED
    row and its missed-growth line stay, and only a person deleting the row releases it."""
    from datetime import timedelta
    from types import SimpleNamespace

    from libs.research import hunt_frontier as hf
    path = tmp_path / "frontier.json"
    monkeypatch.setattr(D, "_frontier_path", lambda: path)
    g = {"name": "g", "site": "ex.example", "language": "en", "region": "x"}
    bare = {"name": "bare", "route": "search", "queries": ["rule"], "language": "en"}
    D._record_frontier([
        {"ground": "g", "status": D.ACCESS_REFUSED, "language": "en",
         "why": "HTTP 403 from ex.example: site held for the run"},
        {"ground": "bare", "status": D.ACCESS_REFUSED, "language": "en",
         "why": "HTTP 429: refused (no site named)"}], [g, bare])
    old = (datetime.now(tz=UTC) - timedelta(days=30)).isoformat()
    raw = json.loads(path.read_text("utf-8"))
    vecs = raw["vectors"]
    for name in ("g", "bare"):
        row = vecs[name] if isinstance(vecs, dict) else next(v for v in vecs if v["name"] == name)
        row["last_attempt"] = old
    path.write_text(json.dumps(raw), "utf-8")
    state = hf.load(path)
    assert hf.BLOCKED_RETRY_D < 30
    for name in ("g", "bare"):
        v = state.vectors[name]
        assert v.person_held and not v.huntable(datetime.now(tz=UTC))[0]
    # hunt_frontier's retry never re-requests it: not "blocked past retry", held for a person
    fr = hf.frontier(state)
    assert {v.name for v in fr["person_held"]} == {"g", "bare"} and not fr["blocked"]
    assert hf.summarise(state)["person_held"] == 2
    # the run seeded from that frontier sends NO request on any route
    calls: list[str] = []

    def no_net(url: str, **k: Any) -> Any:
        calls.append(url)
        return SimpleNamespace(ok=True, status=200, error=None, text="")
    monkeypatch.setattr(D.pf, "get", no_net)
    monkeypatch.setattr(D, "_http", lambda url, *a, **k: calls.append(url) or "")
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    r = D._Run(60.0, True, None, None)
    D.seed_persisted_holds(r, [g, bare], state)
    assert "ex.example" in r.holds.sites and "bare" in r.held_grounds   # fail closed by name
    for gg in ({**g, "route": "http", "url": "https://www.ex.example/a"},
               {**g, "route": "search"}, bare,
               {"name": "sibling", "route": "http", "url": "https://m.ex.example/p"}):
        r.work(gg)
    assert calls == []
    assert r.page("https://sub.ex.example/x") == "" and calls == []
    # a Wayback capture of the held site is held too
    assert r.page("https://web.archive.org/web/2019/https://ex.example/x") == "" and calls == []
    rows = {s["ground"]: s for s in r.status if "ground" in s}
    assert {rows[n]["status"] for n in ("g", "bare", "sibling")} == {"SITE_HELD"}
    assert all(rows[n]["missed_growth"]["delta_elogw"] == "UNMEASURED"
               and "person" in rows[n]["missed_growth"]["unblock"].lower()
               for n in ("g", "bare"))
    # the BLOCKED row is untouched by the held pass (SITE_HELD is not a frontier outcome)
    D._record_frontier(list(r.status), [g, bare])
    after = hf.load(path)
    assert after.vectors["g"].outcome == "BLOCKED" and after.vectors["g"].last_attempt == old
    # THE RELEASE: a person deletes the row; the next run re-seeds it NAMED_ONLY, unheld
    raw = json.loads(path.read_text("utf-8"))
    if isinstance(raw["vectors"], dict):
        raw["vectors"].pop("g")
    else:
        raw["vectors"] = [v for v in raw["vectors"] if v["name"] != "g"]
    path.write_text(json.dumps(raw), "utf-8")
    released = hf.load(path)
    assert "ex.example" not in D.persisted_site_holds([g], released)
    assert "g" not in D.person_held_grounds([g], released)


def test_a_hold_is_persisted_under_the_refusing_domain_and_survives_the_ground(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit PASS5_feb86fa30 MF2: ground g (ex.example) refused by other.example holds
    other.example next run, never the innocent ex.example; the hold is written as its own
    `site:<domain>` vector, so g's next outcome cannot erase it."""
    from libs.research import hunt_frontier as hf
    path = tmp_path / "frontier.json"
    monkeypatch.setattr(D, "_frontier_path", lambda: path)
    g = {"name": "g", "site": "ex.example", "language": "en"}
    D._record_frontier([{"ground": "g", "status": D.ACCESS_REFUSED, "language": "en",
                         "why": "HTTP 403 from other.example: site held for the run"}], [g],
                       {"other.example": {"status": 403, "ground": "g"}})
    held = D.persisted_site_holds([g], hf.load(path))
    assert "other.example" in held and "ex.example" not in held
    assert D.person_held_grounds([g], hf.load(path)) == {}         # the ground is not held
    # g yields on its next run: its own vector moves on, the site hold stays
    D._record_frontier([{"ground": "g", "status": "PRODUCTIVE", "claims": 2}], [g],
                       {"other.example": {"status": 403, "ground": "g", "persisted": True}})
    st = hf.load(path)
    assert st.vectors["g"].outcome == "YIELDED"
    assert set(D.persisted_site_holds([g], st)) == {"other.example"}
    assert st.vectors["site:other.example"].person_held


def test_a_damaged_frontier_fails_closed_and_is_never_overwritten(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "frontier.json"
    path.write_text("{not json", "utf-8")
    monkeypatch.setattr(D, "_frontier_path", lambda: path)
    g = {"name": "g", "site": "ex.example", "language": "en"}
    assert D.frontier_damaged(path)
    assert "ex.example" in D.persisted_site_holds([g], None)
    r = D._Run(60.0, True, None, None)
    D.seed_persisted_holds(r, [g], None)
    monkeypatch.setattr(D, "_http", lambda *a, **k: (_ for _ in ()).throw(AssertionError(a)))
    monkeypatch.setattr(D.pf, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError(a)))
    r.work({"name": "s", "route": "search", "queries": ["q"], "language": "en"})
    assert r.status[-1]["status"] == "SITE_HELD"
    out = D._record_frontier([{"ground": "g", "status": "PRODUCTIVE"}], [g])
    assert out["status"] == "UNMEASURED" and path.read_text("utf-8") == "{not json"


def test_held_site_urls_never_reach_the_crawler_frontier() -> None:
    """Audit PASS5_feb86fa30 MF3: follow() refuses a held site's URL (and a Wayback capture
    of it), and a hold placed AFTER a URL was followed purges it."""
    r = D._Run(60.0, True, None, None)
    r.ground = {"name": "g"}
    r.follow("https://ex.example/a.html", "a", via="t")
    r.follow("https://web.archive.org/web/2019/https://ex.example/b", "b", via="t")
    r.follow("https://ok.example/c", "c", via="t")
    assert len(r.frontier) == 3
    r._hold_site("https://www.ex.example/z", 403)
    assert [u for u, _, _ in r.frontier] == ["https://ok.example/c"]
    r.follow("https://m.ex.example/d", "d", via="t")
    assert [u for u, _, _ in r.frontier] == ["https://ok.example/c"]


def test_an_ip_host_is_held_whole() -> None:
    assert D.registrable_domain("http://10.1.2.3:8080/x") == "10.1.2.3"
    h = D.SiteHolds()
    h.hold("http://10.1.2.3/x", 403)
    assert h.held("http://10.1.2.3/y") and not h.held("http://99.1.2.3/y")


def test_page_and_search_routes_send_no_browser_string_and_never_retry(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    seen: dict[str, Any] = {}

    def get(url: str, **k: Any) -> Any:
        seen.update(k)
        return SimpleNamespace(ok=False, status=429, error="HTTP 429", text="")
    monkeypatch.setattr(D.pf, "get", get)
    with pytest.raises(urllib.error.HTTPError):
        D._http("https://ex.example/a")
    assert seen["retries"] == 0
    ua = seen["headers"]["User-Agent"]
    assert "Mozilla" not in ua and "Chrome" not in ua and ua == D.INDEX_UA


def test_registrable_domain_groups_a_site() -> None:
    assert D.registrable_domain("https://www.ex.example/a") == "ex.example"
    assert D.registrable_domain("sub.ex.example") == "ex.example"
    assert D.registrable_domain("https://news.bbc.co.uk/x") == "bbc.co.uk"
    assert D.registrable_domain("https://a.b.example.com.hk:8443/x") == "example.com.hk"


# HKMA: a multi-day weather closure before 2024 is covered by the untabled-year slack (+3) plus
# the weather day (+1). Since 2024-09-23 HK markets no longer close for weather; that the HKMA
# also PUBLISHES on a typhoon day is an ASSUMPTION (audit PASS5_feb86fa30 SF), not evidence.
@pytest.mark.parametrize(("period", "closed", "true_next"), [
    # Mangkhut-style closure stretched to two days, Mon-Tue
    (date(2018, 9, 14), (date(2018, 9, 17), date(2018, 9, 18)), date(2018, 9, 19)),
    # two-day closure right after the National Day / Mid-Autumn pair (Thu-Fri holidays)
    (date(2020, 9, 30), (date(2020, 10, 5), date(2020, 10, 6)), date(2020, 10, 7)),
    # a three-day closure in a week with no holiday
    (date(2017, 8, 21), (date(2017, 8, 22), date(2017, 8, 23), date(2017, 8, 24)),
     date(2017, 8, 25)),
])
def test_hkma_multi_day_weather_closure_before_2024_is_never_early(
        period: date, closed: tuple[date, ...], true_next: date) -> None:
    src = A.BY_ID["hk_hkma_liquidity"]
    t = src.rule(period)
    assert t >= datetime(true_next.year, true_next.month, true_next.day, 12, tzinfo=UTC)
    assert all(t.date() > d for d in closed)
    assert src.rule_basis is not None and "typhoon" in src.rule_basis(period)


@pytest.mark.parametrize(("period", "typhoon_day"), [
    (date(2025, 9, 23), date(2025, 9, 24)),        # signal 10 (Ragasa): market open since rule
    (date(2024, 11, 13), date(2024, 11, 14)),      # signal 8 (Toraji)
])
def test_hkma_publishes_on_typhoon_days_after_the_2024_rule(period: date,
                                                            typhoon_day: date) -> None:
    """PINS AN ASSUMPTION, NOT EVIDENCE: the rule assumes the HKMA publishes on a post-2024
    typhoon day like any business day. No HKMA release from such a day has been checked; if
    one shows a later publication, this test and the rule change together."""
    src = A.BY_ID["hk_hkma_liquidity"]
    t = src.rule(period)
    # the typhoon day is a business day now; the stamp is its END (20:00 HKT), never before it
    assert t == datetime(typhoon_day.year, typhoon_day.month, typhoon_day.day, 12, tzinfo=UTC)
    assert t > datetime(period.year, period.month, period.day, 23, 59, tzinfo=UTC)
    assert src.rule_basis is not None and "late_bias" not in src.rule_basis(period)
