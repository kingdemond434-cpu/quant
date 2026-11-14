"""Lawful discovery (2026-11-03): the deep-forest grounds are discovered through machine-readable
indexes -- the site's own sitemap and feeds, GDELT DOC 2.0, the Common Crawl URL index and the
Wayback CDX -- instead of scraping Bing and DuckDuckGo, whose anti-bot shells were 139 of the
256 BLOCKED vectors. Every request carries the desk's honest User-Agent, respects robots.txt and
stops on 401/403/429 until a person releases the host. No test opens a socket: the transport is
a fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import deep_forest_miner as dfm  # noqa: E402
from research import discovery_backends as db  # noqa: E402

_CC_COLLINFO = json.dumps([{"id": "CC-MAIN-2026-44",
                            "cdx-api": "https://index.commoncrawl.org/CC-MAIN-2026-44-index"}])
_CC_NDJSON = "\n".join([
    json.dumps({"url": "https://forum.test/thread/usdtry-carry-1", "timestamp": "20261001",
                "mime": "text/html", "status": "200"}),
    json.dumps({"url": "https://forum.test/thread/gone", "timestamp": "20261001",
                "status": "404"}),
    json.dumps({"url": "https://forum.test/static/app.js", "status": "200"}),
    "not json",
])
_WB_JSON = json.dumps([["original", "timestamp", "mimetype", "statuscode"],
                       ["https://forum.test/old/rand-fix", "20190101000000", "text/html", "200"],
                       ["https://forum.test/old/redirect", "20190101000000", "text/html", "301"]])
_GDELT = json.dumps({"articles": [
    {"url": "https://news.test/lira", "title": "Lira weakens after CBRT cut", "seendate":
     "20261101T120000Z", "language": "Turkish", "sourcecountry": "Turkey", "domain": "news.test"}]})
_SITEMAP_INDEX = ("<?xml version='1.0'?><sitemapindex><sitemap><loc>https://forum.test/sm-posts.xml"
                  "</loc></sitemap><sitemap><loc>https://forum.test/sm-tags.xml</loc></sitemap>"
                  "</sitemapindex>")
_SITEMAP = ("<urlset><url><loc>https://forum.test/post/zar-month-end</loc></url>"
            "<url><loc>https://forum.test/logo.png</loc></url></urlset>")
_RSS = ("<rss><channel><item><title>USDTRY carry after the CBRT</title>"
        "<link>https://forum.test/post/9</link><description>carry note</description>"
        "<pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>")


class Net:
    """A fixture transport: url predicate -> (status, body). Records every URL asked for."""

    def __init__(self, routes: list[tuple[str, int, str]] | None = None,
                 default: tuple[int, str] = (404, "")) -> None:
        self.routes = routes or []
        self.default = default
        self.calls: list[str] = []

    def __call__(self, url: str) -> db.Fetched:
        self.calls.append(url)
        for frag, status, body in self.routes:
            if frag in url:
                return db.Fetched(url=url, status=status,
                                  text=body if 200 <= status < 300 else "",
                                  error="" if 200 <= status < 300 else f"HTTP {status}")
        st, body = self.default
        return db.Fetched(url=url, status=st, text=body if 200 <= st < 300 else "",
                          error="" if 200 <= st < 300 else f"HTTP {st}")

    def hosts(self) -> set[str]:
        return {urlparse(u).netloc for u in self.calls}

    def non_robots(self) -> list[str]:
        return [u for u in self.calls if not u.endswith("/robots.txt")]


def _ld(tmp_path: Path, net: Net, **kw) -> db.LawfulDiscovery:
    return db.LawfulDiscovery(net, holds=tmp_path / "holds.json", lock_dir=tmp_path / "locks",
                              sleep=lambda s: None, **kw)


# ----------------------------------------------------------------------------- parsers
def test_common_crawl_cdx_ndjson_keeps_200_page_rows_only() -> None:
    rows = db.parse_cdx_ndjson(_CC_NDJSON)
    assert [r["url"] for r in rows] == ["https://forum.test/thread/usdtry-carry-1",
                                        "https://forum.test/static/app.js"]
    assert rows[0]["timestamp"] == "20261001" and rows[0]["mime"] == "text/html"


def test_wayback_cdx_json_reads_the_header_row_and_skips_redirects() -> None:
    rows = db.parse_wayback_cdx(_WB_JSON)
    assert rows == [{"url": "https://forum.test/old/rand-fix", "timestamp": "20190101000000",
                     "mime": "text/html"}]
    assert db.parse_wayback_cdx("[]") == [] and db.parse_wayback_cdx("<html>") == []


def test_gdelt_doc_rows_and_a_refused_query_is_an_answer_not_a_block() -> None:
    rows, msg = db.parse_gdelt_doc(_GDELT)
    assert msg == "" and rows[0]["url"] == "https://news.test/lira"
    assert rows[0]["published"].startswith("20261101") and rows[0]["country"] == "Turkey"
    rows, msg = db.parse_gdelt_doc("Your search contained a keyword that was too short.")
    assert rows == [] and "without JSON" in msg


def test_sitemap_and_sitemap_index_parse() -> None:
    pages, kids = db.parse_sitemap(_SITEMAP_INDEX)
    assert pages == [] and kids == ["https://forum.test/sm-posts.xml",
                                    "https://forum.test/sm-tags.xml"]
    pages, kids = db.parse_sitemap(_SITEMAP)
    assert "https://forum.test/post/zar-month-end" in pages and kids == []
    assert db.is_feed(_RSS) and not db.is_feed(_SITEMAP)


# ----------------------------------------------------------------------------- the chain
def test_the_lawful_chain_yields_from_every_backend_with_a_record_each(tmp_path) -> None:
    net = Net([("/robots.txt", 404, ""),
               ("forum.test/sitemap.xml", 200, _SITEMAP_INDEX),
               ("sm-posts.xml", 200, _SITEMAP), ("sm-tags.xml", 200, "<urlset></urlset>"),
               ("forum.test/feed", 200, _RSS),
               ("api.gdeltproject.org", 200, _GDELT),
               ("collinfo.json", 200, _CC_COLLINFO),
               ("CC-MAIN-2026-44-index", 200, _CC_NDJSON),
               ("web.archive.org/cdx", 200, _WB_JSON)])
    ld = _ld(tmp_path, net)
    db.ENOUGH_ROWS, saved = 10_000, db.ENOUGH_ROWS                    # run the whole chain
    try:
        d = ld.discover("usdtry carry", site="forum.test", lang="tr", region="tr")
    finally:
        db.ENOUGH_ROWS = saved
    by = {r.backend: r for r in d.records}
    assert set(by) == set(db.LAWFUL_BACKENDS)
    assert all(by[b].status == db.YIELDED for b in db.LAWFUL_BACKENDS), \
        {b: (r.status, r.why) for b, r in by.items()}
    assert d.status == db.YIELDED and set(d.yielded_via) == set(db.LAWFUL_BACKENDS)
    urls = [r["url"] for r in d.rows]
    assert "https://forum.test/post/9" in urls and "https://news.test/lira" in urls
    assert "https://forum.test/old/rand-fix" in urls
    assert not any(u.endswith((".png", ".js")) for u in urls), "assets are not pages"
    # The live crawl id was READ, not assumed; GDELT got the site as a domain query.
    assert any("CC-MAIN-2026-44-index" in u for u in net.calls)
    assert any("domain%3Aforum.test" in u for u in net.calls)
    # Ranked: a row whose url names the query's tokens comes first.
    assert "usdtry" in d.rows[0]["url"] or "usdtry" in d.rows[0].get("title", "").lower()
    # No search engine was ever asked.
    assert not any("bing.com" in h or "duckduckgo" in h for h in net.hosts())


def test_a_site_answer_is_cached_for_the_run(tmp_path) -> None:
    net = Net([("/robots.txt", 404, ""), ("forum.test/feed", 200, _RSS)])
    ld = _ld(tmp_path, net, backends=("site_feeds",))
    ld.discover("q1", site="forum.test")
    n = len(net.calls)
    d2 = ld.discover("q2", site="forum.test")
    assert len(net.calls) == n and d2.status == db.YIELDED


def test_gdelt_without_a_site_names_the_country_and_language(tmp_path) -> None:
    net = Net([("/robots.txt", 404, ""), ("api.gdeltproject.org", 200, _GDELT)])
    ld = _ld(tmp_path, net, backends=("gdelt_doc",))
    d = ld.discover("lira carry", lang="tr", region="tr")
    q = unquote(next(u for u in net.calls if "gdeltproject" in u and "robots" not in u))
    assert "sourcecountry:TU" in q and "sourcelang:turkish" in q and "(lira carry)" in q
    assert d.status == db.YIELDED


# ----------------------------------------------------------------------------- robots
def test_a_robots_disallow_means_no_fetch_on_that_host(tmp_path) -> None:
    net = Net([("forum.test/robots.txt", 200, "User-agent: *\nDisallow: /\n"),
               ("/robots.txt", 404, "")])
    ld = _ld(tmp_path, net, backends=("site_feeds",))
    d = ld.discover("x", site="forum.test")
    assert not [u for u in net.non_robots() if "forum.test" in u], net.calls
    assert d.status == db.BLOCKED and "Disallow" in d.records[0].why


def test_a_disallow_for_our_token_only_is_honoured_and_another_agent_rule_is_not_ours(
        tmp_path) -> None:
    rules = (f"User-agent: {db.DESK_UA_PRODUCT}\nDisallow: /sitemap.xml\n\n"
             "User-agent: OtherBot\nDisallow: /\n")
    net = Net([("forum.test/robots.txt", 200, rules), ("forum.test/feed", 200, _RSS)])
    ld = _ld(tmp_path, net, backends=("site_feeds",))
    d = ld.discover("x", site="forum.test")
    assert "https://forum.test/sitemap.xml" not in net.calls
    assert "https://forum.test/feed" in net.calls and d.status == db.YIELDED


def test_an_unreadable_robots_txt_is_not_consent(tmp_path) -> None:
    net = Net([("/robots.txt", 503, "")])
    ld = _ld(tmp_path, net, backends=("site_feeds",))
    d = ld.discover("x", site="forum.test")
    assert net.non_robots() == [] and d.status == db.BLOCKED


def test_search_engines_are_last_resort_only_and_robots_still_applies(tmp_path) -> None:
    net = Net([("www.bing.com/robots.txt", 200, "User-agent: *\nDisallow: /search\n"),
               ("/robots.txt", 404, ""),
               ("html.duckduckgo.com/html", 200, "<html>anti-bot shell</html>")])
    ld = _ld(tmp_path, net, last_resort=(
        ("bing", dfm._bing_url, dfm.parse_bing), ("duckduckgo", dfm._ddg_url, dfm.parse_ddg)))
    d = ld.discover("lira", site="forum.test", lang="tr", region="tr")
    assert not any("bing.com/search" in u for u in net.calls), "bing robots Disallows /search"
    by = {r.backend: r for r in d.records}
    assert by["bing"].status == db.BLOCKED and not by["bing"].lawful
    assert by["duckduckgo"].status == db.BLOCKED and "no parseable" in by["duckduckgo"].why
    # The lawful backends ran and answered (404 = no sitemap / no captures): the vector is
    # EMPTY, and the engines' refusals are NOT counted against it.
    assert d.status == db.EMPTY
    assert not any(e.startswith(("bing", "duckduckgo")) for e in d.errors())


# ----------------------------------------------------------------------------- hard stops
@pytest.mark.parametrize("status", [401, 403, 429])
def test_401_403_429_hold_the_host_until_a_person_releases_it(tmp_path, status) -> None:
    net = Net([("/robots.txt", 404, ""), ("api.gdeltproject.org/api", status, "")])
    ld = _ld(tmp_path, net, backends=("gdelt_doc",))
    d = ld.discover("lira", region="tr")
    assert d.status == db.BLOCKED and "HARD STOP" in d.records[0].why
    holds = json.loads((tmp_path / "holds.json").read_text("utf-8"))["hosts"]
    assert holds["api.gdeltproject.org"]["status"] == status
    assert holds["api.gdeltproject.org"]["released_by"] is None
    # A fresh run (new process, new caches) does not touch the host at all.
    net2 = Net([("/robots.txt", 404, ""), ("api.gdeltproject.org/api", 200, _GDELT)])
    d2 = _ld(tmp_path, net2, backends=("gdelt_doc",)).discover("other", region="za")
    assert net2.calls == [] and d2.status == db.BLOCKED
    # Only a person releases it.
    holds["api.gdeltproject.org"]["released_by"] = "zuck"
    (tmp_path / "holds.json").write_text(json.dumps({"hosts": holds}), "utf-8")
    d3 = _ld(tmp_path, net2, backends=("gdelt_doc",)).discover("other", region="za")
    assert d3.status == db.YIELDED


def test_a_403_on_robots_txt_is_a_hard_stop_too(tmp_path) -> None:
    net = Net([("forum.test/robots.txt", 403, "")])
    _ld(tmp_path, net, backends=("site_feeds",)).discover("x", site="forum.test")
    assert json.loads((tmp_path / "holds.json").read_text("utf-8"))["hosts"]["forum.test"][
        "status"] == 403
    assert net.non_robots() == []


# ----------------------------------------------------------------------------- honest UA
def test_the_default_transport_sends_the_desk_ua_and_never_retries(monkeypatch) -> None:
    from libs.data import polite_fetch as pf
    seen: dict = {}

    def fake_get(url, **kw):
        seen.update(kw)
        return pf.Response(url=url, status=429, error="HTTP 429")
    monkeypatch.setattr(pf, "get", fake_get)
    r = db.default_transport("https://api.gdeltproject.org/x")
    assert r.status == 429 and seen["retries"] == 0
    ua = seen["headers"]["User-Agent"]
    assert ua.startswith(db.DESK_UA_PRODUCT) and "Mozilla" not in ua


def test_deep_forest_honest_http_uses_the_desk_ua(monkeypatch) -> None:
    from libs.data import polite_fetch as pf
    seen: dict = {}

    def fake_get(url, **kw):
        seen.update(kw)
        return pf.Response(url=url, status=200, text="ok")
    monkeypatch.setattr(pf, "get", fake_get)
    assert dfm._http("https://x.test/", honest=True) == "ok"
    assert seen["headers"]["User-Agent"] == db.DESK_UA and seen["retries"] == 0


# ----------------------------------------------------------------------------- the miner
def _isolate(monkeypatch, tmp_path: Path) -> None:
    for name, val in (("CLAIMS", "claims.jsonl"), ("SEEN", "seen.json"),
                      ("REPORT", "DEEP_FOREST.json"), ("PROVENANCE", "mined.jsonl"),
                      ("DATASETS", "datasets.jsonl"), ("WORLD", "world"),
                      ("COMPETITION_LEDGER", "comp.jsonl")):
        monkeypatch.setattr(dfm, name, tmp_path / val)
    monkeypatch.setattr(dfm, "_feed_frontier", lambda urls: len(urls))
    import research.regime_coverage as rc
    monkeypatch.setattr(rc, "_merge_into_queue", lambda tasks, source="x": None)
    monkeypatch.setattr(dfm, "_universe", lambda: {"USDTRY", "XAUUSD"})
    monkeypatch.setattr(dfm.time, "sleep", lambda s: None)
    monkeypatch.setattr(dfm._Run, "rendered", lambda self, url: "")


def test_a_search_ground_is_discovered_through_the_indexes_and_records_its_backend(
        monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    asked: list[str] = []

    def http(url, **kw):
        asked.append(url)
        if url.endswith("/robots.txt") or "sitemap" in url or "/feed" in url or "rss" in url:
            raise dfm.urllib.error.HTTPError(url, 404, "nf", None, None)  # type: ignore[arg-type]
        if "collinfo" in url:
            return _CC_COLLINFO
        if "CC-MAIN-2026-44-index" in url:
            return _CC_NDJSON
        if "gdeltproject" in url:
            return json.dumps({"articles": []})
        if "web.archive.org" in url:
            return "[]"
        return "<html><body>short</body></html>"
    monkeypatch.setattr(dfm, "_http", http)
    monkeypatch.setattr(dfm, "SOURCES", tmp_path / "src.json")
    (tmp_path / "src.json").write_text(json.dumps({"grounds": [
        {"name": "TR forum", "region": "tr", "language": "tr", "route": "search",
         "site": "forum.test", "queries": ["usdtry carry"], "kind": "forum"}]}), "utf-8")
    doc = dfm.run(budget_s=60, fetch=True)
    g = doc["grounds"][0]
    assert g["discovery_status"] == "YIELDED" and g["engines"] == {"commoncrawl_cdx": 1}
    assert g["discovery"]["commoncrawl_cdx"]["status"] == "YIELDED"
    assert g["discovery"]["gdelt_doc"]["status"] == "EMPTY"
    assert not any("bing.com" in u or "duckduckgo" in u for u in asked)
    assert doc["discovery_backends"]["commoncrawl_cdx"]["YIELDED"] >= 1
    stats = json.loads((tmp_path / dfm.VECTOR_STATS_NAME).read_text("utf-8"))["vectors"]
    assert stats["TR forum"]["yielded_via"] == ["commoncrawl_cdx"]
    assert stats["TR forum"]["discovery_status"] == "YIELDED"
    # The found pages go to the crawler frontier even though their snippets held no claim.
    assert doc["frontier_added"] >= 1
    # Discovery answered, so the ground is not BLOCKED even with no claims.
    assert g["status"] in ("REACHED_NO_CLAIMS", "PRODUCTIVE")


# ----------------------------------------------------------------------------- audit HOLD fixes
def test_a_corrupt_holds_file_holds_every_host_and_is_never_rewritten(tmp_path) -> None:
    holds = tmp_path / "holds.json"
    holds.write_text("{not json", "utf-8")
    net = Net([("/robots.txt", 404, ""), ("api.gdeltproject.org/api", 403, "")])
    ld = _ld(tmp_path, net, backends=("gdelt_doc", "site_feeds"))
    d = ld.discover("lira", site="forum.test", region="tr")
    assert net.calls == [], "UNMEASURED_HOLDS: nothing may be fetched"
    assert d.status == db.BLOCKED and all(db.UNMEASURED_HOLDS in r.why for r in d.records)
    assert ld.holds.status().startswith(db.UNMEASURED_HOLDS)
    with pytest.raises(db.HoldWriteError):
        ld.holds.hold("x.test", 403, "https://x.test/", "t")
    assert holds.read_text("utf-8") == "{not json", "a corrupt file is left exactly as it is"
    # Only a MISSING file means no holds.
    holds.unlink()
    assert db.HostHolds(holds).held("forum.test") == "" and db.HostHolds(holds).status() == ""


def test_a_hold_stops_this_process_at_once_even_when_it_cannot_be_written(tmp_path,
                                                                          monkeypatch) -> None:
    import libs.ops.win_write as ww

    def refuse(tmp, dest, **kw):
        raise PermissionError("held open by a reader")
    monkeypatch.setattr(ww, "replace_resilient", refuse)
    before = len(db.hold_errors())
    net = Net([("/robots.txt", 404, ""), ("api.gdeltproject.org/api", 429, "")])
    ld = _ld(tmp_path, net, backends=("gdelt_doc",))
    d = ld.discover("lira", region="tr")
    assert "HOLD WRITE FAILED" in d.records[0].why
    assert len(db.hold_errors()) == before + 1 and "PermissionError" in db.hold_errors()[-1]
    assert not (tmp_path / "holds.json").exists()
    n = len(net.calls)
    d2 = ld.discover("other words", region="za")            # same process: held locally
    assert len(net.calls) == n and "in this process" in d2.records[0].why


def test_holds_from_concurrent_writers_are_merged_never_lost(tmp_path) -> None:
    import threading
    path = tmp_path / "holds.json"
    hosts = [f"h{i}.test" for i in range(8)]
    # One HostHolds per writer = one per process: only the cross-process lock serialises them.
    ts = [threading.Thread(target=lambda h=h: db.HostHolds(path, lock_dir=tmp_path / "locks")
                           .hold(h, 403, f"https://{h}/", "t")) for h in hosts]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    got = json.loads(path.read_text("utf-8"))["hosts"]
    assert set(got) == set(hosts)
    db.HostHolds(path, lock_dir=tmp_path / "locks").hold("h0.test", 429, "https://h0.test/", "t")
    got = json.loads(path.read_text("utf-8"))["hosts"]
    assert set(got) == set(hosts) and got["h0.test"]["times_held"] == 2


def test_a_5xx_only_site_is_blocked_not_answered(tmp_path) -> None:
    net = Net([("/robots.txt", 404, "")], default=(503, ""))
    d = _ld(tmp_path, net, backends=("site_feeds",)).discover("x", site="forum.test")
    assert d.status == db.BLOCKED and d.answered == 0 and "HTTP 503" in d.records[0].why


def test_the_slot_fails_closed_on_any_other_oserror(tmp_path, monkeypatch) -> None:
    import os as _os

    def boom(*a, **kw):
        raise PermissionError("denied")
    monkeypatch.setattr(_os, "open", boom)
    assert db._cross_process_slot("api.gdeltproject.org", tmp_path, lambda s: None) is False
    monkeypatch.undo()
    assert db._cross_process_slot("api.gdeltproject.org", tmp_path, lambda s: None) is True
    # A stale lock (a crashed holder) is broken; a fresh one is waited on, then refused.
    lock = tmp_path / ".api.gdeltproject.org.slot.lock"
    lock.write_text("", "utf-8")
    _os.utime(lock, (0, 0))
    assert db._cross_process_slot("api.gdeltproject.org", tmp_path, lambda s: None) is True


def test_the_robots_get_takes_the_slot_too(tmp_path, monkeypatch) -> None:
    asked: list[str] = []

    def no_slot(host, lock_dir, sleep):
        asked.append(host)
        return False
    monkeypatch.setattr(db, "_cross_process_slot", no_slot)
    net = Net([("/robots.txt", 404, ""), ("api.gdeltproject.org/api", 200, _GDELT)])
    d = _ld(tmp_path, net, backends=("gdelt_doc",)).discover("lira", region="tr")
    assert net.calls == [] and asked == ["api.gdeltproject.org"]
    assert d.status == db.BLOCKED and "slot" in d.records[0].why


class _Redirecting(Net):
    def __init__(self, routes, redirect: dict[str, tuple[str, int, str]]) -> None:
        super().__init__(routes)
        self.redirect = redirect

    def __call__(self, url: str) -> db.Fetched:
        for frag, (to, status, body) in self.redirect.items():
            if frag in url:
                self.calls.append(url)
                return db.Fetched(url=url, status=status, final_url=to,
                                  text=body if 200 <= status < 300 else "",
                                  error="" if 200 <= status < 300 else f"HTTP {status}")
        return super().__call__(url)


def test_a_redirect_is_rechecked_on_the_target_host_and_the_answering_host_is_held(
        tmp_path) -> None:
    net = _Redirecting([("other.test/robots.txt", 200, "User-agent: *\nDisallow: /\n"),
                        ("/robots.txt", 404, "")],
                       {"forum.test/sitemap.xml": ("https://other.test/sitemap.xml", 200,
                                                   _SITEMAP)})
    d = _ld(tmp_path, net, backends=("site_feeds",)).discover("x", site="forum.test")
    assert "redirected to other.test" in d.records[0].why and not d.rows
    net2 = _Redirecting([("/robots.txt", 404, "")],
                        {"api.gdeltproject.org/api": ("https://refuser.test/x", 403, "")})
    _ld(tmp_path, net2, backends=("gdelt_doc",)).discover("lira", region="tr")
    hosts = json.loads((tmp_path / "holds.json").read_text("utf-8"))["hosts"]
    assert "refuser.test" in hosts and "api.gdeltproject.org" not in hosts


def test_the_miner_transport_reports_the_answering_url(monkeypatch) -> None:
    def fake_http(url, **kw):
        kw["meta"]["final_url"] = "https://moved.test/robots.txt"
        raise dfm.urllib.error.HTTPError("https://moved.test/robots.txt", 403, "x", None, None)  # type: ignore[arg-type]
    monkeypatch.setattr(dfm, "_http", fake_http)
    r = dfm._discovery_transport("https://forum.test/robots.txt")
    assert r.status == 403 and r.final_url == "https://moved.test/robots.txt"


# ------------------------------------------------------------- never-contact hosts (2026-11-14)
def test_youtube_is_discovered_through_the_indexes_never_contacted(tmp_path: Path) -> None:
    """No YouTube contact from the trading box: site_feeds is SKIPPED with the reason, nothing is
    asked of youtube.com (not even robots.txt), and the index backends still find video ids."""
    wb = json.dumps([["original", "timestamp", "mimetype", "statuscode"],
                     ["https://www.youtube.com/watch?v=abcdefghijk", "2026", "text/html", "200"]])
    net = Net([("web.archive.org/cdx", 200, wb), ("/robots.txt", 404, "")])
    d = _ld(tmp_path, net).discover("usdtry carry", site="youtube.com")
    assert not any("youtube.com" in h or "youtu.be" in h for h in net.hosts())
    feeds = next(r for r in d.records if r.backend == "site_feeds")
    assert feeds.status == db.SKIPPED and "YouTube" in feeds.why
    assert any("abcdefghijk" in r["url"] for r in d.rows)


@pytest.mark.parametrize("site", ["fred.stlouisfed.org", "finance.yahoo.com", "www.cboe.com",
                                  "www.cmegroup.com", "www.nasdaq.com", "www.theocc.com",
                                  "mp.weixin.qq.com", "www.baidu.com"])
def test_refused_grounds_are_disabled_with_a_reason(tmp_path: Path, site: str) -> None:
    """Terms-refused and off-limits hosts: no request on any backend, every record SKIPPED
    with the stated reason -- disabled and said, never silently dropped."""
    net = Net(default=(200, ""))
    d = _ld(tmp_path, net).discover("anything", site=site)
    assert net.calls == [] and d.rows == []
    assert d.records and all(r.status == db.SKIPPED and r.why.startswith("REFUSED")
                             for r in d.records)


def test_refused_hosts_are_not_harvested_from_a_keyword_index(tmp_path: Path) -> None:
    """A GDELT keyword answer naming a refused host is not taken: the miner would follow it."""
    g = json.dumps({"articles": [{"url": "https://finance.yahoo.com/news/x", "title": "lira"},
                                 {"url": "https://news.test/lira", "title": "lira"}]})
    net = Net([("api.gdeltproject.org/api", 200, g), ("/robots.txt", 404, "")])
    d = _ld(tmp_path, net).discover("lira", region="tr", lang="tr")
    urls = [r["url"] for r in d.rows]
    assert "https://news.test/lira" in urls and not any("yahoo" in u for u in urls)
    assert db.never_contact("https://www.nasdaq.com/x").startswith("REFUSED")
    assert db.never_contact("https://example.org/x") == ""
