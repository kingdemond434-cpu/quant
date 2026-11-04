"""Landing train step 3: the deep-forest page route (`_http`) and the dataset acquirer
(`acquire_datasets._fetch`) fetch through `polite_fetch.get` -- the desk's honest agent,
robots.txt per origin, and a 401/403/429 hard stop that holds the site. On fixtures; no socket.

Neither can send a browser User-Agent, and each stops on a 403: one page request, then nothing
more to that site (polite_fetch's HostAccess holds it, and the deep forest's own SiteHolds too).
"""
from __future__ import annotations

import email.message
import io
import sys
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402


class _Wire:
    """The network as the polite door sees it: robots.txt is 404 (allow), every other URL 403.
    Records (url, User-Agent) for every request that would have left the box."""

    def __init__(self, page_status: int = 403) -> None:
        self.page_status = page_status
        self.sent: list[tuple[str, str]] = []

    def __call__(self, req: urllib.request.Request, timeout: float = 0, context: Any = None) -> Any:
        ua = req.get_header("User-agent") or ""
        self.sent.append((req.full_url, ua))
        code = 404 if req.full_url.endswith("/robots.txt") else self.page_status
        if code >= 400:
            raise urllib.error.HTTPError(req.full_url, code, "fixture", email.message.Message(),
                                         io.BytesIO(b""))
        hdrs = email.message.Message()
        hdrs["Content-Type"] = "text/csv"
        r = urllib.response.addinfourl(io.BytesIO(b"date,v\n2026-01-01,1\n"), hdrs,
                                       req.full_url, 200)
        return r


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Wire:
    w = _Wire()
    monkeypatch.setattr(pf, "open_no_redirect", w)
    monkeypatch.setattr(pf, "_ACCESS", pf.HostAccess(tmp_path / "access.json"))
    return w


def _honest(w: _Wire) -> None:
    assert w.sent, "nothing was requested"
    for url, ua in w.sent:
        assert ua == pf.DESK_UA, (url, ua)
        assert not pf.looks_like_browser(ua), (url, ua)


def test_deep_forest_page_route_is_honest_and_stops_on_403(wire: _Wire,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    import deep_forest_miner as D
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    # page() follows redirects by hand since pass6-lanes (fetch_hops): its one-request opener
    # is the seam every page byte goes through, so the wire answers there too.
    monkeypatch.setattr(D, "hop_opener", lambda sink: wire)
    r = D._Run(60.0, True, None, None)
    r.ground = {"name": "g"}
    assert r.page("https://ex.example/a.html") == ""
    _honest(wire)
    pages = [u for u, _ in wire.sent if not u.endswith("/robots.txt")]
    assert pages == ["https://ex.example/a.html"]                 # one request, no retry
    # the site is held: by polite_fetch's HostAccess and in this run's SiteHolds
    assert pf.default_access().hold("https://www.ex.example/b")
    assert (r.holds.held("sub.ex.example") or {}).get("status") == 403
    n = len(wire.sent)
    assert r.page("https://ex.example/b.html") == "" and len(wire.sent) == n
    assert D._http.__module__ == D.__name__ and D._UA["User-Agent"] == pf.DESK_UA


def test_deep_forest_http_never_sends_a_browser_string_even_when_asked(
        wire: _Wire) -> None:
    import deep_forest_miner as D
    wire.page_status = 200
    pf.get("https://ok.example/x.csv", headers={"User-Agent": "Mozilla/5.0 Chrome/124"},
           retries=0)
    assert D._http("https://ok.example/y.csv").startswith("date,v")
    _honest(wire)


def test_acquirer_is_honest_and_stops_on_403(wire: _Wire) -> None:
    import acquire_datasets as ad
    raw, why = ad._fetch("https://stats.example.org/series.csv")
    assert raw is None and why == "METHOD_BLOCKED:http_403"
    _honest(wire)
    pages = [u for u, _ in wire.sent if not u.endswith("/robots.txt")]
    assert pages == ["https://stats.example.org/series.csv"]      # one request, no retry
    n = len(wire.sent)
    raw2, why2 = ad._fetch("https://data.stats.example.org/other.csv")   # same site
    assert raw2 is None and why2.startswith("METHOD_BLOCKED") and len(wire.sent) == n
    assert ad._UA == pf.DESK_UA


def test_acquirer_reads_data_with_the_honest_agent(wire: _Wire) -> None:
    import acquire_datasets as ad
    wire.page_status = 200
    raw, ctype = ad._fetch("https://stats.example.org/ok.csv")
    assert raw is not None and raw.startswith(b"date,v") and "csv" in ctype
    _honest(wire)
