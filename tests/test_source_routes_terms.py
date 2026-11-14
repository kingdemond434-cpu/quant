"""The hourly route probe never contacts a host whose terms refuse automated access."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pytest
import scripts.check_source_routes as csr


@pytest.fixture
def opened(monkeypatch):
    urls: list[str] = []

    def fake_urlopen(req, timeout=None):
        urls.append(req.full_url)
        raise OSError("no network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return urls


def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def test_no_probed_url_is_on_a_refused_host(opened, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(csr, "OUT", tmp_path / "SOURCE_ROUTES.json")
    assert csr.main([]) == 0
    assert opened, "the lawful routes are still probed"
    assert not [u for u in opened if _host(u) in csr.REFUSED_HOSTS]
    doc = json.loads((tmp_path / "SOURCE_ROUTES.json").read_text(encoding="utf-8"))
    blocked = {r["name"]: r for r in doc["routes"] if r["status"] == "BLOCKED_ON_TERMS"}
    assert set(blocked) == {"fred_series", "fred_release_dates", "fred_graph_csv",
                            "dukascopy_datafeed", "yahoo_chart"}
    assert all(r["missed_growth"]["verdict"] == "a gap, not a zero" for r in blocked.values())


@pytest.mark.parametrize("url", [
    "https://api.stlouisfed.org/fred/series/observations",
    "https://FRED.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
    "https://datafeed.dukascopy.com:443/datafeed",
    "https://user@query2.finance.yahoo.com/v1/test/getcrumb",
])
def test_a_caller_route_on_a_refused_host_is_refused_by_host(url, opened) -> None:
    # asia_plane brings its own routes; the fence is by host, not by this file's ROUTES.
    out = csr.probe({"name": "caller", "url": url, "expect": "any"})
    assert out["status"] == "BLOCKED_ON_TERMS" and not opened


def test_a_route_marked_refused_is_never_probed(opened) -> None:
    out = csr.probe({"name": "x", "url": "https://example.org/a", "terms": "REFUSED"})
    assert out["status"] == "BLOCKED_ON_TERMS" and not opened


def test_an_unparseable_url_is_refused(opened) -> None:
    out = csr.probe({"name": "x", "url": "https://[bad/a"})
    assert out["status"] == "BLOCKED_ON_TERMS" and not opened
