"""polite_fetch is honest at the source (auditor ruling 2026-10-14).

No caller can make it send a browser User-Agent; robots.txt for the exact origin decides every
request and every redirect hop; unreadable robots means no fetch; 401/403/429 are a hard stop
recorded for the site, never retried and never routed around. Every test runs on a fake opener
that records what was actually sent -- no socket is opened.
"""
from __future__ import annotations

import io
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import regional_survivor_hunters as rsh  # noqa: E402

from libs.data import polite_fetch as pf  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402

_ALLOW = (200, b"User-agent: *\nDisallow:\n", "")
_HTML = b"<html><body>EURUSD carry</body></html>"
_CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/126.0 Safari/537.36")


class _Resp(io.BytesIO):
    def __init__(self, body: bytes, ctype: str) -> None:
        super().__init__(body)
        self.status = 200
        self.url = ""
        self.headers = {"Content-Type": ctype}

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> bool:
        return False


class _Web:
    """URL -> (status, body, location). Unlisted URLs are a network error. Records every request
    with the User-Agent it actually carried."""

    def __init__(self, routes: dict[str, tuple[int, bytes, str]]) -> None:
        self.routes = routes
        self.sent: list[tuple[str, str]] = []

    def __call__(self, req: Any, timeout: float, context: Any = None) -> _Resp:
        url = req.full_url
        self.sent.append((url, str(req.get_header("User-agent"))))
        if url not in self.routes:
            raise urllib.error.URLError("no route in fixture")
        status, body, loc = self.routes[url]
        if status == 200:
            return _Resp(body, "text/plain" if url.endswith("/robots.txt") else "text/html")
        hdrs = Message()
        if loc:
            hdrs["Location"] = loc
        raise urllib.error.HTTPError(url, status, "fixture", hdrs, io.BytesIO(b""))

    def urls(self) -> list[str]:
        return [u for u, _ in self.sent]


def _get(web: _Web, url: str, acc: pf.HostAccess | None = None, **kw: Any) -> pf.Response:
    return pf.get(url, opener=web, gate=None, sleep=lambda s: None,
                  access=acc or pf.HostAccess(path=None), **kw)


# ---------------------------------------------------------------------------- honest identity
@pytest.mark.parametrize("hdr", [{"User-Agent": _CHROME}, {"user-agent": _CHROME},
                                 {"USER-AGENT": "Mozilla/5.0 Gecko/20100101 Firefox/128.0"},
                                 {"User-Agent": "Mozilla/5.0 ... Edg/126.0"}, None])
def test_no_caller_can_make_polite_fetch_send_a_browser_ua(hdr: dict[str, str] | None) -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _HTML, "")})
    r = _get(web, "https://a.test/p", headers=hdr)
    assert r.ok and web.sent
    for _, ua in web.sent:
        assert ua == pf.DESK_UA, ua
        assert not pf.looks_like_browser(ua)


def test_an_honest_caller_ua_is_kept() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _HTML, "")})
    _get(web, "https://a.test/p", headers={"User-Agent": "quant-desk research ops@example.invalid"})
    assert web.sent[-1][1] == "quant-desk research ops@example.invalid"


def test_the_browser_constants_are_gone() -> None:
    assert not hasattr(pf, "BROWSER_UA") and not hasattr(pf, "BROWSER_HEADERS")
    assert not pf.looks_like_browser(pf.DESK_HEADERS["User-Agent"])


def test_the_importers_declare_the_desk_ua() -> None:
    assert rsh.HEADERS["User-Agent"] == pf.DESK_UA
    assert dfm._UA["User-Agent"] == pf.DESK_UA


# ------------------------------------------------------------------------------------ robots
def test_robots_disallow_blocks_the_fetch() -> None:
    web = _Web({"https://a.test/robots.txt": (200, b"User-agent: *\nDisallow: /private\n", ""),
                "https://a.test/private/x": (200, _HTML, "")})
    r = _get(web, "https://a.test/private/x")
    assert not r.ok and r.verdict == "ROBOTS_DISALLOW" and r.status is None
    assert "https://a.test/private/x" not in web.urls()


def test_a_group_naming_the_desk_token_binds_it() -> None:
    web = _Web({"https://a.test/robots.txt": (
        200, f"User-agent: {pf.DESK_UA_PRODUCT}\nDisallow: /\n\nUser-agent: *\nAllow: /\n".encode(),
        ""), "https://a.test/p": (200, _HTML, "")})
    assert _get(web, "https://a.test/p").verdict == "ROBOTS_DISALLOW"
    assert "https://a.test/p" not in web.urls()


@pytest.mark.parametrize("robots", [None, (500, b"", ""), (503, b"", "")])
def test_unreadable_robots_blocks_the_fetch(robots: tuple[int, bytes, str] | None) -> None:
    routes = {"https://a.test/p": (200, _HTML, "")}
    if robots is not None:
        routes["https://a.test/robots.txt"] = robots
    web = _Web(routes)
    r = _get(web, "https://a.test/p")
    assert not r.ok and r.verdict == "ROBOTS_UNREADABLE"
    assert "https://a.test/p" not in web.urls()


@pytest.mark.parametrize("code", [404, 410])
def test_a_missing_robots_allows(code: int) -> None:
    web = _Web({"https://a.test/robots.txt": (code, b"", ""), "https://a.test/p": (200, _HTML, "")})
    assert _get(web, "https://a.test/p").ok


def test_robots_is_cached_per_origin_for_24h() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _HTML, ""),
                "https://a.test/q": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    _get(web, "https://a.test/p", acc)
    _get(web, "https://a.test/q", acc)
    assert web.urls().count("https://a.test/robots.txt") == 1
    assert pf.ROBOTS_TTL_S == 24 * 3600


def test_a_redirect_to_another_origin_checks_that_origins_robots() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW,
                "https://a.test/go": (302, b"", "https://b.test/landing"),
                "https://b.test/robots.txt": (200, b"User-agent: *\nDisallow: /\n", ""),
                "https://b.test/landing": (200, _HTML, "")})
    r = _get(web, "https://a.test/go")
    assert not r.ok and r.verdict == "ROBOTS_DISALLOW"
    assert "https://b.test/robots.txt" in web.urls()
    assert "https://b.test/landing" not in web.urls()


def test_a_permitted_redirect_is_followed_after_its_robots_check() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW,
                "https://a.test/go": (301, b"", "https://b.test:8443/landing"),
                "https://b.test:8443/robots.txt": _ALLOW,
                "https://b.test:8443/landing": (200, _HTML, "")})
    r = _get(web, "https://a.test/go")
    assert r.ok and r.text.startswith("<html>")
    urls = web.urls()
    assert urls.index("https://b.test:8443/robots.txt") < urls.index("https://b.test:8443/landing")


# ------------------------------------------------------------------------------- hard stops
@pytest.mark.parametrize(("status", "verdict"),
                         [(401, "NEEDS_KEY"), (403, "METHOD_BLOCKED"), (429, "METHOD_BLOCKED")])
def test_a_refusal_stops_the_fetch_with_no_retry_and_no_other_route(status: int,
                                                                     verdict: str) -> None:
    web = _Web({"https://www.a.test/robots.txt": _ALLOW,
                "https://www.a.test/p": (status, b"", ""),
                "https://old.a.test/robots.txt": _ALLOW,
                "https://old.a.test/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://www.a.test/p", acc, retries=5)
    assert not r.ok and r.status == status and r.verdict == verdict and r.attempts == 1
    assert web.urls().count("https://www.a.test/p") == 1, "a refused request was retried"
    n = len(web.sent)
    r2 = _get(web, "https://old.a.test/p", acc, retries=5)   # a sibling host: an alternate route
    assert not r2.ok and r2.verdict == verdict and len(web.sent) == n
    assert acc.blocked["a.test"]["status"] == status
    assert pf.stats("default")["refused"] >= 1


def test_a_refusal_is_persisted_for_the_next_process(tmp_path: Path) -> None:
    state = tmp_path / "access.json"
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (403, b"", "")})
    _get(web, "https://a.test/p", pf.HostAccess.load(state))
    again = pf.HostAccess.load(state)
    assert again.hold("https://a.test/other") == "METHOD_BLOCKED"


def test_regional_hunter_stops_a_source_on_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    tried: list[str] = []

    def fake(url: str, timeout: float = 0, *, referer: str = "", accept_json: bool = False) -> str:
        tried.append(url)
        raise rsh.FetchError(url, 403, "METHOD_BLOCKED: HTTP 403", "METHOD_BLOCKED")

    monkeypatch.setattr(rsh, "fetch", fake)
    out = rsh.mine_source("hfm_pamm", rsh.SOURCES["hfm_pamm"], 1)
    assert out["state"] == "refused:METHOD_BLOCKED" and len(tried) == 1, tried


# ------------------------------------------- auditor follow-ups on 1e8cca2ac (2026-10-14)
_CHALLENGE = (b"<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>"
              b"<div id='cf-challenge'>Checking your browser</div></body></html>")


def test_a_crawl_delay_larger_than_the_gap_is_obeyed() -> None:
    web = _Web({"https://a.test/robots.txt": (200, b"User-agent: *\nCrawl-delay: 7\n", ""),
                "https://a.test/p": (200, _HTML, ""), "https://a.test/q": (200, _HTML, "")})
    gate = pf.HostGate(default_s=0.1)
    slept: list[float] = []
    acc = pf.HostAccess(path=None)
    for u in ("https://a.test/p", "https://a.test/q"):
        r = pf.get(u, opener=web, gate=gate, sleep=slept.append, access=acc)
        assert r.ok
    assert slept and max(slept) > 6.5, slept


def test_a_challenge_page_as_robots_is_a_hold_and_nothing_is_fetched() -> None:
    web = _Web({"https://a.test/robots.txt": (200, _CHALLENGE, ""),
                "https://a.test/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://a.test/p", acc)
    assert not r.ok and r.verdict == "METHOD_BLOCKED"
    assert "https://a.test/p" not in web.urls()
    row = acc.blocked["a.test"]
    assert row["verdict"] == "METHOD_BLOCKED" and row["status"] == "WAF"
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED" and row["missed_growth"]["cause"]


def test_an_html_page_as_robots_never_reads_as_allow_all() -> None:
    web = _Web({"https://a.test/robots.txt": (200, b"<html><body>Not found</body></html>", ""),
                "https://a.test/p": (200, _HTML, "")})
    r = _get(web, "https://a.test/p")
    assert not r.ok and "https://a.test/p" not in web.urls()


def test_a_challenge_page_as_content_is_held_and_not_ingested() -> None:
    web = _Web({"https://a.test/robots.txt": _ALLOW, "https://a.test/p": (200, _CHALLENGE, ""),
                "https://a.test/q": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    r = _get(web, "https://a.test/p", acc)
    assert not r.ok and r.text == "" and r.verdict == "METHOD_BLOCKED"
    assert acc.hold("https://a.test/q") == "METHOD_BLOCKED"
    n = len(web.sent)
    assert not _get(web, "https://a.test/q", acc).ok and len(web.sent) == n


def test_a_github_io_tenants_refusal_does_not_hold_its_neighbour() -> None:
    web = _Web({"https://a.github.io/robots.txt": _ALLOW,
                "https://a.github.io/p": (403, b"", ""),
                "https://b.github.io/robots.txt": _ALLOW,
                "https://b.github.io/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    assert _get(web, "https://a.github.io/p", acc).verdict == "METHOD_BLOCKED"
    assert _get(web, "https://b.github.io/p", acc).ok
    assert pf.site_of("x.blogspot.com") != pf.site_of("y.blogspot.com")
    assert pf.site_of("a.lausd.k12.ca.us") != pf.site_of("b.sfusd.k12.ca.us")
    assert pf.site_of("www.example.co.uk") == pf.site_of("old.example.co.uk") == "example.co.uk"


def test_an_ip_is_held_by_its_full_host() -> None:
    web = _Web({"http://10.1.2.3/robots.txt": _ALLOW, "http://10.1.2.3/p": (403, b"", ""),
                "http://10.9.2.3/robots.txt": _ALLOW, "http://10.9.2.3/p": (200, _HTML, "")})
    acc = pf.HostAccess(path=None)
    _get(web, "http://10.1.2.3/p", acc)
    assert "10.1.2.3" in acc.blocked and pf.site_of("10.1.2.3") == "10.1.2.3"
    assert _get(web, "http://10.9.2.3/p", acc).ok
