"""One terms-refused host list, matched by domain suffix, reaches every automated-contact path."""
from __future__ import annotations

import importlib
import io
import socket
import sys
import urllib.request
from pathlib import Path

import pytest

from libs.data import refused_hosts as rh

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("url", [
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
    "https://ALFRED.stlouisfed.org./series",
    "https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/05/03/14h_ticks.bi5",
    "https://www.dukascopy.com/swiss/english/marketwatch/historical/",
    "https://user:pw@query2.finance.yahoo.com:443/v1/test/getcrumb",
    "https://web.archive.org/web/2024/https://example.org/",
    "https://m.youtube.com/watch?v=x",
    "https://www.cboe.com/us/options/",
    "https://[bad/",
    "",
])
def test_refused(url: str) -> None:
    assert rh.refusal(url)


@pytest.mark.parametrize("url", [
    "https://publicreporting.cftc.gov/resource/6dca-aqww.json",
    "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml",
    "https://notdukascopy.com/",                 # a suffix match is on a dot boundary
    "https://yahoo.com.example.org/",
])
def test_allowed(url: str) -> None:
    assert rh.refusal(url) is None


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a refused host was contacted")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_the_canaries_never_contact_a_refused_host(no_network, monkeypatch) -> None:
    import scripts.run_canaries as rc
    contacted: list[str] = []
    monkeypatch.setattr(rc, "_get", lambda url: contacted.append(url) or (0, "offline"))
    monkeypatch.setattr(rc, "_baselines", dict)
    results = rc.run_all()
    assert not [u for u in contacted if rh.refusal(u)]
    assert results["C8"]["verdict"] == "BLOCKED_ON_TERMS"
    assert results["C8"]["missed_growth"]["verdict"] == "a gap, not a zero"


def _crawler():
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "side_channels"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module("world_crawler")


def test_the_crawler_never_fetches_or_seeds_a_refused_host(no_network, monkeypatch) -> None:
    wc = _crawler()
    raw, why = wc.fetch("https://live-login.dukascopy.com/cabinet/trader/?lang=en")
    assert raw is None and why.startswith("BLOCKED_ON_TERMS")
    assert not [u for u in wc.SEEDS if rh.refusal(u)]
    monkeypatch.setattr(wc, "frontier_seeds", lambda: ("https://fred.stlouisfed.org/",))
    monkeypatch.setattr(wc, "paid_substitute_seeds",
                        lambda: ("https://www.dukascopy.com/swiss/english/marketwatch/sentiment/",))
    added: list[str] = []
    monkeypatch.setattr(wc.wf, "add", lambda sources, url, via="": added.append(url) or True)
    wc.seed({})
    assert added and not [u for u in added if rh.refusal(u)]


@pytest.mark.parametrize("url", [
    "https://comtradeapi.un.org/data/v1/get/C/A/HS",
    "https://comtradeplus.un.org/",
    "https://www.theice.com/marketdata/reports",
])
def test_the_other_ruled_hosts_are_refused(url: str) -> None:
    assert rh.refusal(url)


def test_a_redirect_to_a_refused_host_is_never_followed() -> None:
    handler = rh.RefusingRedirectHandler()
    req = urllib.request.Request("https://lawful.example.org/a")
    with pytest.raises(rh.RefusedRedirect) as exc:
        handler.redirect_request(req, io.BytesIO(), 302, "Found", {},
                                 "https://datafeed.dukascopy.com/datafeed")
    assert "BLOCKED_ON_TERMS" in str(exc.value.reason)
    nxt = handler.redirect_request(req, io.BytesIO(), 302, "Found", {}, "https://lawful.example.org/b")
    assert nxt is not None and nxt.full_url == "https://lawful.example.org/b"


def test_the_crawler_reports_a_refused_redirect_as_blocked(monkeypatch) -> None:
    wc = _crawler()

    class _Opener:
        def open(self, req, timeout=None):
            raise rh.RefusedRedirect("BLOCKED_ON_TERMS: redirect target refused (test)")

    monkeypatch.setattr(wc, "_refusing_opener", lambda: _Opener())
    raw, why = wc.fetch("https://lawful.example.org/a")
    assert raw is None and why.startswith("BLOCKED_ON_TERMS")
