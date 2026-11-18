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
    def do_GET(self) -> None:
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


# ------------------------------------------------- reddit (audit MF1) and the honest UA (SF1) --
HONEST = "quant-desk-research/1.0 (automated research; honours robots.txt)"


def test_reddit_is_on_the_shared_list_with_its_clause() -> None:
    from libs.data.refused_hosts import refusal
    for url in ("https://www.reddit.com/r/algotrading/hot.json", "https://oauth.reddit.com/x",
                "https://old.reddit.com/r/Forex/.rss", "https://redd.it/abc"):
        why = refusal(url)
        assert why and "Reddit" in why, url
    assert "monetized" in (refusal("https://www.reddit.com/") or "")
    assert refusal("https://notreddit.com/") is None


def test_reddit_hot_is_unmeasured_never_an_empty_list(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    def no_socket(*a: object, **k: object) -> None:
        raise AssertionError("reddit was contacted")
    monkeypatch.setattr(fd, "_refusing_opener", no_socket)
    got = fd.reddit_hot("algotrading")
    assert isinstance(got, fd.Unmeasured) and got.status == "UNMEASURED"
    assert "BLOCKED_ON_TERMS" in got.reason and "Reddit" in got.reason
    rec = fd.blocked_on_terms()
    assert any("reddit.com" in u and r["status"] == "BLOCKED_ON_TERMS" for u, r in rec.items())


def test_crowding_records_reddit_unmeasured_not_zero_posts() -> None:
    from research import crowding_miner as cm
    act = cm.reddit_activity_of(fd.Unmeasured("BLOCKED_ON_TERMS: x"))
    assert act == {"status": "UNMEASURED", "reason": "BLOCKED_ON_TERMS: x"}
    assert "posts" not in act
    live = cm.reddit_activity_of([{"score": 4, "num_comments": 2}, {"score": 2, "num_comments": 1}])
    assert live == {"posts": 2, "avg_score": 3.0, "comments": 3}


def test_the_user_agent_is_honest_and_never_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    assert fd.UA == HONEST
    src = Path(fd.__file__).read_text("utf-8")
    assert "Mozilla" not in src
    sent: list[str | None] = []

    class _Resp:
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def read(self) -> bytes:
            return b"{}"

    class _Opener:
        def open(self, req: urllib.request.Request, timeout: int = 0) -> _Resp:
            sent.append(req.get_header("User-agent"))
            return _Resp()

    monkeypatch.setattr(fd, "_refusing_opener", lambda: _Opener())
    fd._get("https://example.org/a", headers={"User-Agent": "Mozilla/5.0 spoof"})
    fd._get("https://example.org/b", headers={"Accept": "application/json"})
    fd.github_search("gold")
    assert sent == [HONEST, HONEST, HONEST]


def test_reddit_miner_sends_nothing_and_writes_nothing(monkeypatch: pytest.MonkeyPatch,
                                                       tmp_path: Path) -> None:
    import sys
    side = str(Path(fd.__file__).resolve().parents[1] / "side_channels")
    monkeypatch.syspath_prepend(side)
    import reddit_miner as rm

    def no_get(*a: object, **k: object) -> None:
        raise AssertionError("reddit was contacted")
    monkeypatch.setattr(rm.requests, "get", no_get)
    monkeypatch.setattr(rm, "OUT", tmp_path)
    assert rm.blocked_on_terms()
    assert rm.mine_subreddit("Forex") == []
    assert rm.run_and_save() == []
    assert list(tmp_path.iterdir()) == []
    assert "Mozilla" not in rm.HEADERS["User-Agent"]
    sys.modules.pop("reddit_miner", None)


def test_free_stack_reddit_is_blocked_on_terms_not_empty() -> None:
    from datetime import UTC, datetime

    from libs.data import free_stack as fs

    def no_fetch(*a: object, **k: object) -> bytes:
        raise AssertionError("reddit was contacted")
    h = fs.fetch_reddit(no_fetch, {"id": "reddit", "subreddits": ["Gold"]}, {"seen_ids": ["a"]},
                        datetime(2026, 11, 18, tzinfo=UTC))
    assert h.status == "BLOCKED_ON_TERMS" and "Reddit" in h.detail
    assert h.requests == 0 and h.cursor == {"seen_ids": ["a"]}
