"""Pass-5 lanes, on fixtures, with no network.

F4  HKMA interbank liquidity (Convertibility Undertaking flow, Aggregate Balance, HIBOR) through
    alt_proxies' hourly leg and exogenous_conditioner path.
N6  the Wikipedia attention row extended to ja/tr/es/pt/ko currency and crisis articles, under
    the Wikimedia User-Agent policy.
GAP1 USAJOBS posting counts (key and e-mail in headers only, first-seen PIT); Adzuna HELD.
F2  FINRA Reg SHO short volume HELD on FINRA's own terms.
GAP2 congressional PTR trades parsed (ticker, side, band, transaction and filing dates) and the
    congress row HELD on the statute the disclosure gate prints.
GAP3 deep_forest's non-Bing site-index route (sitemap, else Common Crawl CDX), robots-gated.

Every fixture is SYNTHETIC (values illustrative, never the publisher's).
"""
from __future__ import annotations

import json
import sys
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


def _by(obs: list[A.Obs], series: str) -> dict[date, float]:
    return {o.period: o.value for o in obs if o.series == series}


# ============================================================================ terms
def test_pass5_rows_carry_their_terms_verdicts_and_verbatim_quotes() -> None:
    for sid in LIVE:
        assert A.BY_ID[sid].terms == "confirmed", sid
    for sid in HELD:
        src = A.BY_ID[sid]
        assert src.terms == "refused" and src.parse is None, sid
        assert A.status_of(src).startswith("BLOCKED_ON_TERMS"), sid
        assert "HELD, NEVER FETCHED" in src.note, sid
    for sid in (*LIVE, *HELD):
        ev = A.TERMS_EVIDENCE[sid]
        assert ev["terms_url"].startswith("https://") and len(ev["terms_quote"]) > 60, sid
        assert ev["checked_at"] == "2026-10-14", sid
    assert "commercial or noncommercial" in A.TERMS_EVIDENCE["us_usajobs_postings"]["terms_quote"]
    assert "non-commercial" in A.TERMS_EVIDENCE["us_finra_regsho_short_volume"]["terms_quote"]
    assert "14 day trial" in A.TERMS_EVIDENCE["gb_adzuna_vacancies"]["terms_quote"]
    wiki = A.TERMS_EVIDENCE["wiki_asia_attention"]
    assert "User-Agent" in wiki["api_terms_quote"] and "contact" in wiki["ua_policy_quote"]


def test_held_rows_are_never_fetched(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    for sid in HELD:
        rec = A.collect(paths, A.BY_ID[sid], {}, NOW, fetch=True, fixtures=None, deadline=1e18,
                        getter=lambda *a: (_ for _ in ()).throw(AssertionError("fetched")))
        assert rec["requests"] == 0 and rec["status"].startswith("BLOCKED_ON_TERMS"), sid


def test_pass5_instruments_exist_and_no_crypto_exchange_host() -> None:
    uni = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for sid in (*LIVE, *HELD, "wiki_asia_attention"):
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
    assert src.instruments_for("hkma_cu_flow_mn") == {"USDHKD": -1, "HK50": 1, "CHINAH": 1,
                                                      "USDCNH": -1}
    assert src.instruments_for("hkma_hibor_1m")["HK50"] == -1
    # PIT: never before the next weekday's HK morning
    assert src.rule(date(2026, 10, 9)) == datetime(2026, 10, 12, 2, tzinfo=UTC)


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
        assert sid in rep["blocked_on_terms"]


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


def test_congress_row_is_held_on_the_disclosure_statute(tmp_path: Path) -> None:
    from free_stack_hunter import Store, run
    doc = json.loads((DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    row = next(r for r in doc["sources"] if r["id"] == "congress_trades")
    assert row["terms"] == "refused" and "commercial purpose" in row["terms_quote"]
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"sources": [row]}), "utf-8")
    store = Store(tmp_path)
    rep = run(budget_s=30, fetch=lambda *a: (_ for _ in ()).throw(AssertionError("fetched")),
              store=store, roster=roster, now=NOW, live=False)
    per = rep["per_source"]["congress_trades"]
    assert per["status"] == "HELD_ON_TERMS" and "commercial purpose" in per["last_error"]


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
