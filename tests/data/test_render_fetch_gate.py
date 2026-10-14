"""render_fetch judges what the browser actually fetched (auditor must-fix 2, 2026-10-14).

* `page.goto`'s status is read: 401/403/429 record the site hold and NO content is returned.
* `page.route` never sees redirect hops, so the navigation's request chain
  (`request.redirected_from`) is re-checked: a hop that robots.txt disallows, or a held site,
  discards the content.
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


def test_a_redirect_hop_robots_disallows_discards_the_content() -> None:
    acc = _Access({"https://b.test": "User-agent: *\nDisallow: /secret\n"})
    page = _Page(_Response(["https://a.test/p", "https://b.test/secret"]))
    html, err = _drive(page, acc)
    assert html == "" and "ROBOTS_DISALLOW" in err and "redirect hop" in err


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


def test_a_script_navigation_to_a_disallowed_page_is_refused() -> None:
    acc = _Access({"https://a.test": "User-agent: *\nDisallow: /private\n"})
    page = _Page(_Response(["https://a.test/p"]))
    page.url = "https://a.test/private/after-js"
    html, err = _drive(page, acc)
    assert html == "" and "ROBOTS_DISALLOW" in err


def test_judge_navigation_with_no_response_is_permitted() -> None:
    assert rf.judge_navigation(None, "https://a.test/#frag", _Access()) == ""
