"""The world crawler fetches politely: an honest User-Agent, robots.txt per origin, and a hard stop.

Auditor ruling 2026-10-14: browser impersonation is forbidden, robots.txt decides every fetch, and
401/403/429 stop the site for the run with no route around it. Every test here runs on a fake
opener -- no socket is opened -- and records every request the crawler tried to send.
"""
from __future__ import annotations

import json
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import world_crawler as wc  # noqa: E402

_HTML = b"<html><body><p>EURUSD H4 breakout</p></body></html>"


class _Resp:
    def __init__(self, body: bytes, ctype: str) -> None:
        self._body = body
        self.headers = {"Content-Type": ctype}

    def read(self, n: int = -1) -> bytes:
        return self._body if n < 0 else self._body[:n]

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        return None


class _Web:
    """URL -> (status, body, location). Anything unlisted is a network error."""

    def __init__(self, routes: dict[str, tuple[int, bytes, str]]) -> None:
        self.routes = routes
        self.sent: list[tuple[str, str]] = []

    def __call__(self, req: Any, timeout: float) -> _Resp:
        url = req.full_url
        self.sent.append((url, str(req.get_header("User-agent"))))
        if url not in self.routes:
            raise urllib.error.URLError("no route in fixture")
        status, body, loc = self.routes[url]
        if status == 200:
            ctype = "text/plain" if url.endswith("/robots.txt") else "text/html; charset=utf-8"
            return _Resp(body, ctype)
        hdrs = Message()
        if loc:
            hdrs["Location"] = loc
        raise urllib.error.HTTPError(url, status, "fixture", hdrs, None)

    def urls(self) -> list[str]:
        return [u for u, _ in self.sent]


def _install(monkeypatch: pytest.MonkeyPatch, routes: dict[str, tuple[int, bytes, str]]) -> _Web:
    web = _Web(routes)
    monkeypatch.setattr(wc, "_open", web)
    return web


def _access() -> wc.HostAccess:
    return wc.HostAccess(path=None, now=1_000_000.0)


_ALLOW = (200, b"User-agent: *\nDisallow:\n", "")


# ------------------------------------------------------------------------------- honest identity
def test_the_user_agent_sent_never_impersonates_a_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {"https://a.test/robots.txt": _ALLOW,
                                 "https://a.test/page": (200, _HTML, "")})
    raw, why = wc.fetch("https://a.test/page", _access())
    assert raw == _HTML and why == ""
    assert web.sent, "the fixture saw no request"
    for _, ua in web.sent:
        for token in ("Mozilla", "Chrome", "Safari", "AppleWebKit", "Gecko"):
            assert token not in ua, f"browser token {token!r} in UA {ua!r}"
        assert ua.startswith("quant-mt5-research-desk/") and "github.com" in ua
    assert "Mozilla" not in wc.UA and "Chrome" not in wc.UA


# ------------------------------------------------------------------------------------- robots
# LAWS 5e (live): robots.txt is an ACCESS LABEL, never a refusal ("robots.txt Disallow treated as
# a refusal" is in access_classifier.REMOVED_BRAKES). The crawler reads it, fetches, and the
# label lands on the access record and on the discovery row.
def test_a_disallowed_path_is_fetched_and_labelled(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {
        "https://a.test/robots.txt": (200, b"User-agent: *\nDisallow: /private\n", ""),
        "https://a.test/private/x": (200, _HTML, ""),
        "https://a.test/open": (200, _HTML, "")})
    acc = _access()
    raw, why = wc.fetch("https://a.test/private/x", acc)
    assert raw == _HTML and why == ""
    assert "https://a.test/private/x" in web.urls()
    assert acc.access_label("https://a.test/private/x")["access_label"] == "PUBLIC_WITH_TERMS"
    assert acc.labelled["https://a.test"]["access_label"] == "PUBLIC_WITH_TERMS"
    assert wc.fetch("https://a.test/open", acc)[0] == _HTML
    assert acc.access_label("https://a.test/open")["access_label"] == "PUBLIC"
    assert web.urls().count("https://a.test/robots.txt") == 1, "robots is cached per origin"
    assert acc.summary()["robots_disallowed"] == 1


def test_the_discovery_row_carries_the_robots_label() -> None:
    page = {"title": "t", "symbols": ["XAUUSD"], "timeframes": [], "patterns": ["breakout"],
            "lang": "en", "links": [], "claims": []}
    lab = {"access_label": "PUBLIC_WITH_TERMS", "terms_note": "robots.txt Disallow",
           "redistribute_allowed": False}
    row = wc.to_discovery("https://a.test/private/x", page, "abc", terms_note="registry note",
                          access=lab)
    assert row is not None
    assert row["access_label"] == "PUBLIC_WITH_TERMS" and row["redistribute_allowed"] is False
    assert row["terms_note"] == "registry note; robots.txt Disallow"


def test_a_group_naming_this_crawler_labels_it(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {
        "https://a.test/robots.txt": (
            200, b"User-agent: quant-mt5-research-desk\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
            ""),
        "https://a.test/page": (200, _HTML, "")})
    acc = _access()
    assert wc.fetch("https://a.test/page", acc) == (_HTML, "")
    assert acc.access_label("https://a.test/page")["access_label"] == "PUBLIC_WITH_TERMS"
    assert "https://a.test/page" in web.urls()


def test_a_subdomain_needs_its_own_robots(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {
        "https://a.test/robots.txt": _ALLOW,
        "https://a.test/page": (200, _HTML, ""),
        "https://sub.a.test/robots.txt": (200, b"User-agent: *\nDisallow: /\n", ""),
        "https://sub.a.test/page": (200, _HTML, "")})
    acc = _access()
    assert wc.fetch("https://a.test/page", acc)[0] == _HTML
    raw, why = wc.fetch("https://sub.a.test/page", acc)
    assert raw == _HTML and why == ""
    assert "https://sub.a.test/robots.txt" in web.urls(), "the parent's robots was reused"
    assert acc.access_label("https://sub.a.test/page")["access_label"] == "PUBLIC_WITH_TERMS"
    assert acc.access_label("https://a.test/page")["access_label"] == "PUBLIC"


def test_a_port_is_its_own_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {"https://a.test/robots.txt": _ALLOW,
                                 "https://a.test:8443/robots.txt": _ALLOW,
                                 "https://a.test:8443/p": (200, _HTML, "")})
    assert wc.fetch("https://a.test:8443/p", _access())[0] == _HTML
    assert "https://a.test:8443/robots.txt" in web.urls()
    assert "https://a.test/robots.txt" not in web.urls()


@pytest.mark.parametrize("robots", [None, (500, b"", ""), (503, b"", "")])
def test_unreadable_robots_is_fetched_as_access_unclear(monkeypatch: pytest.MonkeyPatch,
                                                        robots: tuple[int, bytes, str] | None
                                                        ) -> None:
    routes = {"https://a.test/page": (200, _HTML, ""), "https://a.test/other": (200, _HTML, "")}
    if robots is not None:
        routes["https://a.test/robots.txt"] = robots
    web = _install(monkeypatch, routes)
    acc = _access()
    raw, why = wc.fetch("https://a.test/page", acc)
    assert raw == _HTML and why == ""
    assert "https://a.test/page" in web.urls()
    assert acc.access_label("https://a.test/page")["access_label"] == "ACCESS_UNCLEAR"
    assert acc.labelled["https://a.test"]["access_label"] == "ACCESS_UNCLEAR"
    # and it is not re-asked within the run
    wc.fetch("https://a.test/other", acc)
    assert web.urls().count("https://a.test/robots.txt") == 1
    assert "https://a.test" not in acc.robots, "an unreadable robots must not be cached as rules"


def test_a_404_robots_means_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {"https://a.test/robots.txt": (404, b"", ""),
                                 "https://a.test/page": (200, _HTML, "")})
    assert wc.fetch("https://a.test/page", _access()) == (_HTML, "")
    assert "https://a.test/page" in web.urls()


def test_the_robots_cache_lives_24h(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    web = _install(monkeypatch, {"https://a.test/robots.txt": _ALLOW,
                                 "https://a.test/page": (200, _HTML, "")})
    state = tmp_path / "access.json"
    acc = wc.HostAccess(path=state, now=1_000_000.0)
    wc.fetch("https://a.test/page", acc)
    acc.save()
    again = wc.HostAccess.load(state)
    again._now = 1_000_000.0 + 3600
    wc.fetch("https://a.test/page", again)
    assert web.urls().count("https://a.test/robots.txt") == 1, "fresh cache was re-fetched"
    stale = wc.HostAccess.load(state)
    stale._now = 1_000_000.0 + wc.ROBOTS_TTL_S + 1
    wc.fetch("https://a.test/page", stale)
    assert web.urls().count("https://a.test/robots.txt") == 2, "stale cache was trusted"


# ------------------------------------------------------------------------------- hard stops
@pytest.mark.parametrize(("status", "verdict"),
                         [(401, "NEEDS_KEY"), (403, "METHOD_BLOCKED"), (429, "METHOD_BLOCKED")])
def test_a_refusal_stops_the_site_and_nothing_else(monkeypatch: pytest.MonkeyPatch,
                                                   status: int, verdict: str) -> None:
    web = _install(monkeypatch, {
        "https://www.a.test/robots.txt": _ALLOW,
        "https://www.a.test/p1": (status, b"", ""),
        "https://www.a.test/p2": (200, _HTML, ""),
        "https://old.a.test/robots.txt": _ALLOW,
        "https://old.a.test/p1": (200, _HTML, ""),
        "https://b.test/robots.txt": _ALLOW,
        "https://b.test/p": (200, _HTML, "")})
    acc = _access()
    raw, why = wc.fetch("https://www.a.test/p1", acc)
    assert raw is None and why.startswith(verdict)
    sent_before = len(web.sent)
    # Same host, a sibling subdomain (an alternate route) and the bare domain: nothing is sent.
    for url in ("https://www.a.test/p2", "https://old.a.test/p1", "https://a.test/p"):
        r, w = wc.fetch(url, acc)
        assert r is None and w == verdict
    assert len(web.sent) == sent_before, f"requests sent after a {status}: {web.sent[sent_before:]}"
    assert web.urls().count("https://www.a.test/p1") == 1, "a refused request was retried"
    # Another site is untouched.
    assert wc.fetch("https://b.test/p", acc)[0] == _HTML
    row = acc.blocked["a.test"]
    assert row["verdict"] == verdict and row["status"] == status
    assert "recheck_after_ts" not in row and row["released_by"] is None
    assert row["key"] == "site:a.test" and row["waits_for"] == "a person"


def test_a_429_and_a_403_both_wait_for_a_person_never_a_clock(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, {"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (429, b"", ""),
                           "https://b.test/robots.txt": _ALLOW, "https://b.test/p": (403, b"", "")})
    state = tmp_path / "access.json"
    acc = wc.HostAccess(path=state, now=1_000_000.0)
    wc.fetch("https://a.test/p", acc)
    wc.fetch("https://b.test/p", acc)
    acc.save()
    later = wc.HostAccess.load(state)
    later._now = 1_000_000.0 + 400 * 86400.0
    assert later.hold("https://a.test/x") == "METHOD_BLOCKED", "a 429 hold lapsed on a clock"
    assert later.hold("https://b.test/x") == "METHOD_BLOCKED", "a 403 lapsed on a clock"
    saved = json.loads(state.read_text("utf-8"))
    assert saved["blocked"]["a.test"]["waits_for"] == "a person"
    assert saved["blocked"]["b.test"]["waits_for"] == "a person"


def test_a_refused_robots_read_holds_the_site(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {"https://a.test/robots.txt": (403, b"", ""),
                                 "https://a.test/page": (200, _HTML, "")})
    acc = _access()
    raw, why = wc.fetch("https://a.test/page", acc)
    assert raw is None and why == "METHOD_BLOCKED"
    assert "https://a.test/page" not in web.urls()


# ------------------------------------------------------------------------------- redirects
def test_a_cross_host_redirect_reads_the_new_hosts_robots_as_a_label(
        monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {
        "https://a.test/robots.txt": _ALLOW,
        "https://a.test/go": (302, b"", "https://c.test/landing"),
        "https://c.test/robots.txt": (200, b"User-agent: *\nDisallow: /landing\n", ""),
        "https://c.test/landing": (200, _HTML, "")})
    acc = _access()
    raw, why = wc.fetch("https://a.test/go", acc)
    assert raw == _HTML and why == ""
    assert "https://c.test/robots.txt" in web.urls()
    assert "https://c.test/landing" in web.urls()
    assert acc.labelled["https://c.test"]["access_label"] == "PUBLIC_WITH_TERMS"


def test_a_permitted_cross_host_redirect_is_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {
        "https://a.test/robots.txt": _ALLOW,
        "https://a.test/go": (301, b"", "https://c.test/landing"),
        "https://c.test/robots.txt": _ALLOW,
        "https://c.test/landing": (200, _HTML, "")})
    assert wc.fetch("https://a.test/go", _access()) == (_HTML, "")
    assert web.urls().index("https://c.test/robots.txt") < web.urls().index(
        "https://c.test/landing")


def test_a_redirect_into_a_held_site_is_not_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {
        "https://c.test/robots.txt": _ALLOW, "https://c.test/x": (403, b"", ""),
        "https://a.test/robots.txt": _ALLOW,
        "https://a.test/go": (302, b"", "https://c.test/landing")})
    acc = _access()
    wc.fetch("https://c.test/x", acc)
    raw, why = wc.fetch("https://a.test/go", acc)
    assert raw is None and why == "METHOD_BLOCKED"
    assert "https://c.test/landing" not in web.urls()


# ------------------------------------------------------------------------------- the crawl loop
def test_the_crawl_never_asks_a_held_site_again(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    import world_frontier as wf
    web = _install(monkeypatch, {
        "https://a.test/robots.txt": _ALLOW, "https://a.test/1": (403, b"", ""),
        "https://a.test/2": (200, _HTML, ""), "https://a.test/3": (200, _HTML, ""),
        "https://b.test/robots.txt": _ALLOW, "https://b.test/1": (200, _HTML, "")})
    sources = {u: wf.Source(url=u, host=u.split("/")[2])
               for u in ("https://a.test/1", "https://a.test/2", "https://a.test/3",
                         "https://b.test/1")}
    monkeypatch.setattr(wf, "load", lambda *a, **k: sources)
    monkeypatch.setattr(wf, "save", lambda *a, **k: None)
    monkeypatch.setattr(wf, "due", lambda s, b: list(s.values()))
    monkeypatch.setattr(wc, "seed", lambda s: 0)
    # The optional seat and the share registry stay out of a no-network test.
    monkeypatch.setitem(sys.modules, "libs.research.proposer_seat", None)
    monkeypatch.setitem(sys.modules, "research.source_shares", None)
    monkeypatch.setattr(wc, "ACCESS_STATE", tmp_path / "access.json")
    monkeypatch.setattr(wc, "REPORT", tmp_path / "world_crawl.json")
    monkeypatch.setattr(wc, "WORLD", tmp_path / "world")
    monkeypatch.setattr(wc, "BASE", tmp_path)
    monkeypatch.setattr(wc, "VAULT", tmp_path / "world" / "vault")
    report = wc.crawl(budget=4, run_budget_s=60, seconds_per_host=0.0)
    assert "https://a.test/2" not in web.urls() and "https://a.test/3" not in web.urls()
    assert "https://b.test/1" in web.urls()
    assert report["access"]["holds"]["a.test"]["verdict"] == "METHOD_BLOCKED"
    assert report["failures"].get("HELD METHOD_BLOCKED") == 2
    saved = json.loads((tmp_path / "access.json").read_text("utf-8"))
    assert saved["blocked"]["a.test"]["status"] == 403


# ------------------------------------------- auditor follow-ups on 1e8cca2ac (2026-10-14)
#: A challenge is recognised by its MARKUP (Cloudflare's bootstrap), never by its title text.
_CHALLENGE = (b"<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>"
              b"<script>window._cf_chl_opt={cvId:'3'};</script></body></html>")


def _crawl_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, urls: tuple[str, ...]) -> None:
    import world_frontier as wf
    sources = {u: wf.Source(url=u, host=u.split("/")[2]) for u in urls}
    monkeypatch.setattr(wf, "load", lambda *a, **k: sources)
    monkeypatch.setattr(wf, "save", lambda *a, **k: None)
    monkeypatch.setattr(wf, "due", lambda s, b: list(s.values()))
    monkeypatch.setattr(wc, "seed", lambda s: 0)
    monkeypatch.setitem(sys.modules, "libs.research.proposer_seat", None)
    monkeypatch.setitem(sys.modules, "research.source_shares", None)
    monkeypatch.setattr(wc, "ACCESS_STATE", tmp_path / "access.json")
    monkeypatch.setattr(wc, "REPORT", tmp_path / "world_crawl.json")
    monkeypatch.setattr(wc, "WORLD", tmp_path / "world")
    monkeypatch.setattr(wc, "BASE", tmp_path)
    monkeypatch.setattr(wc, "VAULT", tmp_path / "world" / "vault")


def test_the_crawl_obeys_a_crawl_delay_larger_than_its_gap(monkeypatch: pytest.MonkeyPatch,
                                                           tmp_path: Path) -> None:
    _install(monkeypatch, {"https://a.test/robots.txt": (200, b"User-agent: *\nCrawl-delay: 9\n",
                                                         ""),
                           "https://a.test/1": (200, _HTML, ""),
                           "https://a.test/2": (200, _HTML + b"2", "")})
    _crawl_fixture(monkeypatch, tmp_path, ("https://a.test/1", "https://a.test/2"))
    slept: list[float] = []
    monkeypatch.setattr(wc.time, "sleep", slept.append)
    wc.crawl(budget=2, run_budget_s=60, seconds_per_host=wc.HOST_GAP_S)
    assert slept and max(slept) > 8.0, f"the 9s Crawl-delay was not obeyed: {slept}"


def test_a_challenge_robots_is_a_hold_and_no_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    web = _install(monkeypatch, {"https://a.test/robots.txt": (200, _CHALLENGE, ""),
                                 "https://a.test/page": (200, _HTML, "")})
    acc = _access()
    raw, why = wc.fetch("https://a.test/page", acc)
    assert raw is None and why == "METHOD_BLOCKED"
    assert "https://a.test/page" not in web.urls()
    assert acc.blocked["a.test"]["missed_growth"]["delta_elogw"] == "UNMEASURED"


def test_a_challenge_page_is_not_ingested_and_is_held(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"https://a.test/robots.txt": _ALLOW,
                           "https://a.test/page": (200, _CHALLENGE, "")})
    acc = _access()
    raw, why = wc.fetch("https://a.test/page", acc)
    assert raw is None and why.startswith("METHOD_BLOCKED")
    assert acc.hold("https://a.test/other") == "METHOD_BLOCKED"


def test_a_github_io_refusal_holds_only_that_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"https://a.github.io/robots.txt": _ALLOW,
                           "https://a.github.io/p": (403, b"", ""),
                           "https://b.github.io/robots.txt": _ALLOW,
                           "https://b.github.io/p": (200, _HTML, "")})
    acc = _access()
    wc.fetch("https://a.github.io/p", acc)
    assert wc.fetch("https://b.github.io/p", acc) == (_HTML, "")
    assert wc.site_of("10.1.2.3") == "10.1.2.3"


def test_a_hold_survives_a_run_that_raises_mid_loop(monkeypatch: pytest.MonkeyPatch,
                                                    tmp_path: Path) -> None:
    _install(monkeypatch, {"https://a.test/robots.txt": _ALLOW,
                           "https://a.test/1": (403, b"", ""),
                           "https://b.test/robots.txt": _ALLOW,
                           "https://b.test/1": (200, _HTML, "")})
    _crawl_fixture(monkeypatch, tmp_path, ("https://a.test/1", "https://b.test/1"))

    def killed(url: str, raw: bytes) -> str:
        raise RuntimeError("killed mid-loop")
    monkeypatch.setattr(wc, "vault", killed)
    with pytest.raises(RuntimeError):
        wc.crawl(budget=2, run_budget_s=60, seconds_per_host=0.0)
    saved = json.loads((tmp_path / "access.json").read_text("utf-8"))
    assert saved["blocked"]["a.test"]["status"] == 403
    assert wc.HostAccess.load(tmp_path / "access.json").hold("https://a.test/9") == "METHOD_BLOCKED"
