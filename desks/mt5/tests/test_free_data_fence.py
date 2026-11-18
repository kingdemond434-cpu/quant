"""free_data's network calls go through the refused-hosts fence, and nothing else changes.

The BoJ refusal is STUBBED here (#1346 adds boj.or.jp to the shared list); the redirect test uses
a host the shared list already refuses, so both halves are pinned without the two PRs stacking.
"""
from __future__ import annotations

import http.server
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from research import free_data as fd

BOJ = "https://www.boj.or.jp/en/announcements/rss.rdf"
FEED = (b'<?xml version="1.0"?><rss><channel><item><title>Rate decision</title>'
        b"<link>http://x/1</link><pubDate>Mon, 16 Nov 2026 05:00:00 GMT</pubDate></item>"
        b"</channel></rss>")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (stdlib name)
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "https://fred.stlouisfed.org/graph/fredgraph.csv")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml")
        self.send_header("Content-Length", str(len(FEED)))
        self.end_headers()
        self.wfile.write(FEED)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy",
                "ALL_PROXY"):
        monkeypatch.delenv(var, raising=False)
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fd, "CACHE", tmp_path)
    monkeypatch.setattr(fd, "_BLOCKED", {})


def _refuse_boj(monkeypatch: pytest.MonkeyPatch) -> None:
    def stub(url: str) -> str | None:
        return "BoJ: stubbed refusal" if "boj.or.jp" in url else None
    monkeypatch.setattr(fd, "_refusal", stub)

    def no_socket(*a: object, **k: object) -> None:
        raise AssertionError("a refused host was contacted")
    monkeypatch.setattr(fd, "_refusing_opener", no_socket)


def test_boj_is_not_polled_and_says_why() -> None:
    assert "BOJ" not in fd.RSS_FEEDS
    assert not any("boj.or.jp" in u for u in fd.RSS_FEEDS.values())
    row = fd.RSS_UNMEASURED["BOJ"]
    assert row["status"] == "UNMEASURED" and "BLOCKED_ON_TERMS" in row["reason"]


def test_a_refused_feed_is_recorded_not_requested(monkeypatch: pytest.MonkeyPatch,
                                                   tmp_path: Path) -> None:
    _refuse_boj(monkeypatch)
    got = fd.rss_fetch(BOJ)
    assert isinstance(got, fd.Unmeasured) and got == []
    assert got.status == "UNMEASURED" and "BLOCKED_ON_TERMS" in got.reason
    assert fd.blocked_on_terms()[BOJ]["status"] == "BLOCKED_ON_TERMS"
    assert (tmp_path / "blocked_on_terms.json").exists()


def test_a_refused_get_raises_never_a_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_boj(monkeypatch)
    with pytest.raises(fd.BlockedOnTerms):
        fd._get(BOJ)
    assert BOJ in fd.blocked_on_terms()


def test_the_shared_list_is_consulted_before_the_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_socket(*a: object, **k: object) -> None:
        raise AssertionError("a refused host was contacted")
    monkeypatch.setattr(fd, "_refusing_opener", no_socket)
    with pytest.raises(fd.BlockedOnTerms):
        fd._get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
    assert fd.yahoo_daily("^VIX") is None


def test_an_unrefused_host_is_byte_identical(server: str) -> None:
    url = server + "/feed.xml"
    req = urllib.request.Request(url, headers={"User-Agent": fd.UA})
    with urllib.request.urlopen(req, timeout=5) as r:
        direct = r.read()
    assert fd._get(url, timeout=5) == direct == FEED
    items = fd.rss_fetch(url)
    assert type(items) is list
    assert items == [{"title": "Rate decision", "link": "http://x/1",
                      "pubDate": "Mon, 16 Nov 2026 05:00:00 GMT"}]
    assert fd.blocked_on_terms() == {}


def test_a_redirect_to_a_refused_host_is_never_followed(server: str) -> None:
    with pytest.raises(urllib.error.URLError, match="BLOCKED_ON_TERMS"):
        fd._get(server + "/redirect", timeout=5)
