"""The onion transport: .onion only, allowlist only, robots fail-closed, TOR_ABSENT is a state.

Fixtures only -- no socket is opened and no .onion host is ever contacted from these tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data import onion_fetch as OF  # noqa: E402

HOST = "a" * 56 + ".onion"
FEED = f"http://{HOST}/feed.xml"
ROW = {"id": "x", "onion_host": HOST, "feed_urls": [FEED], "attachments": True}
PRESENT = {"status": OF.TOR_PRESENT, "proxy": "socks5h://127.0.0.1:9050"}


class _Transport:
    def __init__(self, answers: dict[str, tuple[int, str, bytes]]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url, headers, timeout, proxy):
        self.calls.append((url, proxy))
        assert OF.onion_host(url), f"a non-onion URL reached the transport: {url}"
        return self.answers.get(url, (404, "text/plain", b""))


def _fetcher(transport, status=PRESENT, rows=(ROW,), fetchable=True):
    return OF.OnionFetcher(rows=rows, status=status, transport=transport,
                           is_fetchable=lambda r: fetchable, min_interval_s=0.0,
                           sleep=lambda s: None)


@pytest.mark.parametrize("url", [
    "https://www.bbc.co.uk/news", "http://example.com/a.onion", "ftp://" + HOST + "/x",
    "http://user:pw@" + HOST + "/", "http://" + "a" * 16 + ".onion/", "http://127.0.0.1:9050/",
    "https://" + HOST + ".evil.com/"])
def test_clearnet_and_malformed_urls_are_refused_before_any_socket(url):
    with pytest.raises(OF.OnionRefused):
        OF.require_onion(url)
    t = _Transport({})
    res = _fetcher(t).fetch(url)
    assert res.verdict in ("CLEARNET_REFUSED",) and t.calls == []


def test_v3_onion_hosts_and_subdomains_pass():
    assert OF.require_onion(FEED) == HOST
    assert OF.onion_host(f"https://www.{HOST}/x") == f"www.{HOST}"


def test_only_the_allowlisted_url_is_fetched_never_a_neighbour():
    t = _Transport({f"http://{HOST}/robots.txt": (404, "", b""),
                    FEED: (200, "application/rss+xml", b"<rss/>")})
    f = _fetcher(t)
    assert f.fetch(FEED).ok
    other = f.fetch(f"http://{HOST}/elsewhere.html")
    assert other.verdict == "NOT_ALLOWLISTED"
    assert [u for u, _p in t.calls] == [f"http://{HOST}/robots.txt", FEED]
    assert all(p == PRESENT["proxy"] for _u, p in t.calls)


def test_a_row_that_is_not_fetchable_is_refused():
    t = _Transport({})
    assert _fetcher(t, fetchable=False).fetch(FEED).verdict == "ROW_NOT_FETCHABLE"
    assert t.calls == []


def test_tor_absent_is_a_reported_state_not_a_crash():
    t = _Transport({})
    st = OF.tor_status(env={}, connect=lambda *a, **k: (_ for _ in ()).throw(OSError("no")),
                       find=lambda name: None)
    assert st["status"] == OF.TOR_ABSENT and "missed_growth" in st["missed_growth"]
    assert st["tried"] == ["127.0.0.1:9050", "127.0.0.1:9150"]
    res = _fetcher(t, status=st).fetch(FEED)
    assert res.verdict == OF.TOR_ABSENT and t.calls == []


class _Sock:
    def __init__(self, reply: bytes) -> None:
        self.reply = reply

    def sendall(self, b):
        assert b == b"\x05\x01\x00"

    def recv(self, n):
        return self.reply

    def close(self):
        pass


def test_socks_absent_when_tor_answers_but_no_client_library():
    st = OF.tor_status(env={"QUANT_TOR_SOCKS": "127.0.0.1:9150"},
                       connect=lambda *a, **k: _Sock(b"\x05\x00"), find=lambda name: None)
    assert st["status"] == OF.SOCKS_ABSENT and st["proxy"] == "socks5h://127.0.0.1:9150"
    assert "missed_growth" in st["missed_growth"]
    ok = OF.tor_status(env={}, connect=lambda *a, **k: _Sock(b"\x05\x00"),
                       find=lambda name: object())
    assert ok["status"] == OF.TOR_PRESENT
    not_socks = OF.tor_status(env={}, connect=lambda *a, **k: _Sock(b"HT"),
                              find=lambda name: object())
    assert not_socks["status"] == OF.TOR_ABSENT


def test_robots_unreadable_fails_closed_and_disallow_is_honoured():
    t = _Transport({f"http://{HOST}/robots.txt": (500, "", b"")})
    assert _fetcher(t).fetch(FEED).verdict == "ROBOTS_REFUSED"
    t2 = _Transport({f"http://{HOST}/robots.txt": (200, "text/plain",
                                                    b"User-agent: *\nDisallow: /\n"),
                     FEED: (200, "", b"x")})
    assert _fetcher(t2).fetch(FEED).verdict == "ROBOTS_REFUSED"
    assert FEED not in [u for u, _p in t2.calls]


def test_hard_stop_statuses_stop_the_host_and_redirects_are_not_followed():
    t = _Transport({f"http://{HOST}/robots.txt": (404, "", b""), FEED: (429, "", b"")})
    f = _fetcher(t)
    assert f.fetch(FEED).verdict == "HARD_STOP"
    n = len(t.calls)
    assert f.fetch(FEED).verdict == "HARD_STOP" and len(t.calls) == n
    t2 = _Transport({f"http://{HOST}/robots.txt": (404, "", b""), FEED: (302, "", b"")})
    assert _fetcher(t2).fetch(FEED).verdict == "REDIRECT_NOT_FOLLOWED"


def test_attachments_text_csv_pdf_only_and_size_capped():
    assert OF.attachment_allowed(f"http://{HOST}/a.csv", "text/csv", 1000) is None
    assert OF.attachment_allowed(f"http://{HOST}/a.pdf", "application/pdf", 10) is None
    assert "TYPE" in OF.attachment_allowed(f"http://{HOST}/a.exe", "", 10)
    assert "TYPE" in OF.attachment_allowed(f"http://{HOST}/a.zip", "application/zip", 10)
    assert "TOO_LARGE" in OF.attachment_allowed(f"http://{HOST}/a.txt", "text/plain", 10**8)
    assert "UNKNOWN" in OF.attachment_allowed(f"http://{HOST}/a.txt", "text/plain", None)
    t = _Transport({})
    f = _fetcher(t)
    assert f.fetch(f"http://{HOST}/x.exe", attachment=True, size=10).verdict == \
        "ATTACHMENT_REFUSED"
    other = "b" * 56 + ".onion"
    assert f.fetch(f"http://{other}/a.txt", attachment=True, size=10).verdict == \
        "NOT_ALLOWLISTED"


def test_the_user_agent_is_honest():
    assert "quant-desk-research" in OF.UA and "Mozilla" not in OF.UA
