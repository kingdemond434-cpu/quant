"""render_fetch judges what the browser actually fetched (auditor must-fix 2, 2026-10-14).

* `page.goto`'s status is read: 401/403/429 record the site hold and NO content is returned.
* `page.route` never sees redirect hops, so the navigation's request chain
  (`request.redirected_from`) is re-checked: a held site discards the content; a hop robots.txt
  disallows is fetched and LABELLED PUBLIC_WITH_TERMS (LAWS 5e: a label, never a refusal).
* A challenge (markup, `cf-mitigated`, a Cloudflare 503) is held; prose is not a challenge.
Fake page/response objects only: no browser, no socket.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.data import polite_fetch as pf
from libs.data import render_fetch as rf


class _Req:
    def __init__(self, url: str, redirected_from: _Req | None = None) -> None:
        self.url = url
        self.redirected_from = redirected_from


class _Response:
    def __init__(self, chain: list[str], status: int = 200,
                 headers: dict[str, str] | None = None) -> None:
        req: _Req | None = None
        for u in chain:
            req = _Req(u, req)
        assert req is not None
        self.request = req
        self.url = chain[-1]
        self.status = status
        self.headers = headers or {}


class _Page:
    def __init__(self, response: _Response | None, html: str = "<html><body>ok</body></html>"
                 ) -> None:
        self.response = response
        self.html = html
        self.url = response.url if response is not None else ""
        self.routed = False
        self.waited = False

    def route(self, pattern: str, handler: Any) -> None:
        self.routed = True

    def set_default_timeout(self, ms: float) -> None:
        pass

    def goto(self, url: str, **kw: Any) -> _Response | None:
        return self.response

    def wait_for_selector(self, sel: str, timeout: float = 0) -> None:
        self.waited = True

    def wait_for_timeout(self, ms: int) -> None:
        self.waited = True

    def content(self) -> str:
        return self.html


class _Access(pf.HostAccess):
    """HostAccess with robots answered from a dict: origin -> robots text (absent = allow)."""

    def __init__(self, robots: dict[str, str] | None = None) -> None:
        super().__init__(path=None)
        self._robots = robots or {}

    def _read_robots(self, origin: str, send: Any) -> dict[str, Any]:
        if origin in self._robots:
            return {"state": "rules", "text": self._robots[origin]}
        return {"state": "allow_all"}


def _drive(page: _Page, acc: pf.HostAccess, url: str = "https://a.test/p") -> tuple[str, str]:
    return rf._drive(page, url, acc, wait_selector="", timeout_s=1.0, wait_ms=1)


def test_a_plain_render_returns_its_content() -> None:
    page = _Page(_Response(["https://a.test/p"]))
    html, err = _drive(page, _Access())
    assert err == "" and "ok" in html and page.routed


def test_a_403_on_the_render_is_held_and_returns_nothing() -> None:
    for code, verdict in ((401, "NEEDS_KEY"), (403, "METHOD_BLOCKED"), (429, "METHOD_BLOCKED")):
        acc = _Access()
        page = _Page(_Response(["https://www.a.test/p"], status=code),
                     html="<html>error page body</html>")
        html, err = _drive(page, acc, "https://www.a.test/p")
        assert html == "" and verdict in err and f"HTTP {code}" in err
        assert acc.hold("https://other.a.test/x") == verdict
        assert not page.waited                       # nothing read after the refusal


def test_a_redirect_hop_robots_disallows_keeps_the_content_and_is_labelled() -> None:
    """LAWS 5e: robots.txt is a LABEL, never a refusal."""
    acc = _Access({"https://b.test": "User-agent: *\nDisallow: /secret\n"})
    page = _Page(_Response(["https://a.test/p", "https://b.test/secret"]))
    html, err = _drive(page, acc)
    assert err == "" and "ok" in html
    assert acc.labelled["https://b.test"]["access_label"] == "PUBLIC_WITH_TERMS"
    assert acc.label_counts.get("PUBLIC_WITH_TERMS", 0) >= 1


def test_a_redirect_through_a_held_site_discards_the_content() -> None:
    acc = _Access()
    acc.block("https://held.test/x", 403)
    page = _Page(_Response(["https://a.test/p", "https://www.held.test/q",
                            "https://c.test/landing"]))
    html, err = _drive(page, acc)
    assert html == "" and "METHOD_BLOCKED" in err


def test_a_cloudflare_503_challenge_is_held_not_returned() -> None:
    acc = _Access()
    page = _Page(_Response(["https://a.test/p"], status=503, headers={"cf-mitigated": "challenge"}),
                 html="<html><script>window._cf_chl_opt={}</script></html>")
    html, err = _drive(page, acc)
    assert html == "" and "CHALLENGED" in err
    assert acc.hold("https://a.test/q") == "METHOD_BLOCKED"


def test_challenge_markup_on_a_200_is_held_but_prose_is_content() -> None:
    acc = _Access()
    page = _Page(_Response(["https://a.test/p"]),
                 html='<html><form id="challenge-form" action="/x?__cf_chl_tk=1"></form></html>')
    html, err = _drive(page, acc)
    assert html == "" and "CHALLENGED" in err and acc.hold("https://a.test/q")
    acc2 = _Access()
    prose = "<html><p>Just a moment... access denied, captcha, are you a robot?</p></html>"
    html2, err2 = _drive(_Page(_Response(["https://a.test/p"]), html=prose), acc2)
    assert err2 == "" and html2 == prose and not acc2.blocked


def test_a_script_navigation_to_a_disallowed_page_is_kept_and_labelled() -> None:
    acc = _Access({"https://a.test": "User-agent: *\nDisallow: /private\n"})
    page = _Page(_Response(["https://a.test/p"]))
    page.url = "https://a.test/private/after-js"
    html, err = _drive(page, acc)
    assert err == "" and "ok" in html
    assert acc.labelled["https://a.test"]["access_label"] == "PUBLIC_WITH_TERMS"


def test_judge_navigation_with_no_response_is_permitted() -> None:
    assert rf.judge_navigation(None, "https://a.test/#frag", _Access()) == ""


# ------------------------------------------- request-level interception (audit 6eb7a91b4 SF)
class _Fetched:
    def __init__(self, status: int, location: str = "") -> None:
        self.status = status
        self.headers = {"location": location} if location else {}
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class _Net:
    """What actually went out: url -> (status, Location). Every fetch is recorded."""

    def __init__(self, routes: dict[str, tuple[int, str]]) -> None:
        self.routes = routes
        self.sent: list[str] = []

    def fetch(self, url: str) -> _Fetched:
        self.sent.append(url)
        status, loc = self.routes.get(url, (200, ""))
        return _Fetched(status, loc)


class _RouteReq:
    def __init__(self, url: str, nav: bool) -> None:
        self.url = url
        self._nav = nav

    def is_navigation_request(self) -> bool:
        return self._nav


class _Route:
    """Playwright's Route as `_gate` uses it: fetch (redirects off), fulfill, abort."""

    def __init__(self, url: str, net: _Net, nav: bool = True) -> None:
        self.request = _RouteReq(url, nav)
        self.net = net
        self.fulfilled: _Fetched | None = None
        self.aborted = ""

    def fetch(self, url: str | None = None, max_redirects: int | None = None) -> _Fetched:
        assert max_redirects == 0, "the gate must never let a fetch follow a redirect itself"
        return self.net.fetch(url or self.request.url)

    def fulfill(self, response: _Fetched) -> None:
        self.fulfilled = response

    def abort(self, reason: str = "") -> None:
        self.aborted = reason or "aborted"


class _RoutedPage(_Page):
    """A page whose goto runs the installed route handler, as Chromium would."""

    def __init__(self, net: _Net) -> None:
        super().__init__(None)
        self.net = net
        self.handler: Any = None
        self.subresources: list[_Route] = []

    def route(self, pattern: str, handler: Any) -> None:
        self.routed = True
        self.handler = handler

    def goto(self, url: str, **kw: Any) -> _Response | None:
        r = _Route(url, self.net)
        self.handler(r)
        if r.aborted:
            raise RuntimeError("net::ERR_BLOCKED_BY_CLIENT")
        assert r.fulfilled is not None
        self.url = url
        return _Response([url], status=r.fulfilled.status)

    def load_subresource(self, url: str) -> _Route:
        r = _Route(url, self.net, nav=False)
        self.handler(r)
        self.subresources.append(r)
        return r


def test_a_redirect_hop_robots_disallows_is_requested_and_labelled() -> None:
    acc = _Access({"https://b.test": "User-agent: *\nDisallow: /secret\n"})
    net = _Net({"https://a.test/p": (302, "https://b.test/secret")})
    html, err = _drive(_RoutedPage(net), acc)
    assert err == "" and "ok" in html
    assert net.sent == ["https://a.test/p", "https://b.test/secret"], "the hop was not followed"
    assert acc.labelled["https://b.test"]["access_label"] == "PUBLIC_WITH_TERMS"


def test_a_redirect_hop_into_a_held_site_is_never_requested() -> None:
    acc = _Access()
    acc.block("https://held.test/x", 403)
    net = _Net({"https://a.test/p": (301, "https://www.held.test/q")})
    html, err = _drive(_RoutedPage(net), acc)
    assert html == "" and "METHOD_BLOCKED" in err
    assert net.sent == ["https://a.test/p"]


def test_a_redirect_into_a_terms_held_source_is_never_requested() -> None:
    net = _Net({"https://a.test/p": (302, "https://nitter.net/x/rss")})
    html, err = _drive(_RoutedPage(net), _Access())
    assert html == "" and "TERMS-FENCED" in err and net.sent == ["https://a.test/p"]


def test_permitted_hops_are_each_checked_then_fetched_and_only_the_end_is_returned() -> None:
    net = _Net({"https://a.test/p": (302, "/q"), "https://a.test/q": (307, "https://c.test/r")})
    page = _RoutedPage(net)
    html, err = _drive(page, _Access())
    assert err == "" and "ok" in html
    assert net.sent == ["https://a.test/p", "https://a.test/q", "https://c.test/r"]


def test_a_429_at_a_hop_holds_the_site_that_refused_not_the_first_one() -> None:
    acc = _Access()
    net = _Net({"https://a.test/p": (302, "https://c.test/r"), "https://c.test/r": (429, "")})
    html, err = _drive(_RoutedPage(net), acc)
    assert html == "" and "HTTP 429" in err
    assert acc.hold("https://c.test/other") == "METHOD_BLOCKED"
    assert acc.hold("https://a.test/other") == ""


def test_the_first_request_under_a_disallow_goes_out_labelled() -> None:
    acc = _Access({"https://a.test": "User-agent: *\nDisallow: /p\n"})
    net = _Net({})
    html, err = _drive(_RoutedPage(net), acc)
    assert err == "" and "ok" in html and net.sent == ["https://a.test/p"]
    assert acc.labelled["https://a.test"]["access_label"] == "PUBLIC_WITH_TERMS"


def test_the_first_request_to_a_held_site_is_refused_before_it_goes_out() -> None:
    acc = _Access()
    acc.block("https://a.test/x", 403)
    net = _Net({})
    html, err = _drive(_RoutedPage(net), acc)
    assert html == "" and "METHOD_BLOCKED" in err and net.sent == []


def test_a_robots_disallowed_subresource_is_fetched_and_labelled() -> None:
    acc = _Access({"https://cdn.test": "User-agent: *\nDisallow: /\n"})
    net = _Net({})
    page = _RoutedPage(net)
    _html, err = _drive(page, acc)
    assert err == ""
    r = page.load_subresource("https://cdn.test/x.js")
    assert not r.aborted and "https://cdn.test/x.js" in net.sent
    assert acc.labelled["https://cdn.test"]["access_label"] == "PUBLIC_WITH_TERMS"


def test_a_refused_subresource_is_aborted_without_failing_the_page() -> None:
    acc = _Access()
    acc.block("https://cdn.test/y", 403)
    net = _Net({})
    page = _RoutedPage(net)
    _html, err = _drive(page, acc)
    assert err == ""
    r = page.load_subresource("https://cdn.test/x.js")
    assert r.aborted and "https://cdn.test/x.js" not in net.sent
