"""mql5 is a per-source policy row, not a ban; the METHOD fence holds for every source.

Principal ruling 2026-10-13: "no source should be banned". The mql5 category refusal is retired --
its harvesters and crawler seeds are back as they run LIVE -- and mql5.com is IDEAS_ONLY (its ToU
3.7 names automated access, so an mql5 page is never live input). What stays off is the method:
`polite_fetch.fenced_urlopen` refuses a redirect into a login / CAPTCHA wall, keeps every redirect
hop visible, and the shared client inflates a compressed body only up to its cap. No test here
opens a socket off the loopback.
"""
from __future__ import annotations

import gzip
import http.server
import sys
import threading
from pathlib import Path
from typing import Any, ClassVar

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "side_channels"), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from side_channels import mql5_terms  # noqa: E402

from libs.data import polite_fetch as pf  # noqa: E402

#: The LIVE call sites the auditor named; each must go through the ONE fenced door.
CALL_SITES = (
    "desks/mt5/side_channels/world_crawler.py",
    "desks/mt5/research/moat_collectors.py",
    "desks/mt5/research/index_discovery.py",
    "desks/mt5/research/source_fixer.py",
    "desks/mt5/side_channels/global_survivor_frontier.py",
    "desks/mt5/research/asia_collector.py",
)


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Loopback server: /wall 302s to /accounts/login, /hop 302s to /ok, /ok answers 200."""

    class _H(http.server.BaseHTTPRequestHandler):
        hits: ClassVar[list[str]] = []

        def do_GET(self) -> None:
            _H.hits.append(self.path)
            if self.path.startswith("/wall"):
                self.send_response(302)
                self.send_header("Location", "/accounts/login?next=/data")
                self.end_headers()
            elif self.path.startswith("/hop"):
                self.send_response(301)
                self.send_header("Location", "/ok")
                self.end_headers()
            else:
                body = b"<html><body>public page</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *_a: Any) -> None:
            return

    for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    _H.hits = []
    srv = http.server.HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", _H.hits
    srv.shutdown()
    srv.server_close()


# ----------------------------------------------------------------------------- the policy row
def test_mql5_is_ideas_only_never_banned() -> None:
    row = mql5_terms.POLICY
    assert row["status"] == "IDEAS_ONLY" and row["why"]
    assert row["live_input"] is False and mql5_terms.is_live_input_permitted() is False
    assert "BLOCKED" not in row["status"] and "PROHIBIT" not in row["status"]
    assert "automated means" in row["clauses"]["3.7"]       # the clause is kept, verbatim
    assert not hasattr(mql5_terms, "guard") and not hasattr(mql5_terms, "refuse")


def test_mql5_harvesters_and_seeds_are_back() -> None:
    crawler = (DESK / "side_channels" / "world_crawler.py").read_text(encoding="utf-8")
    assert "https://www.mql5.com/" in crawler
    seeds = (DESK / "side_channels" / "seed_miners.py").read_text(encoding="utf-8")
    assert "def mine_mql5_signals" in seeds
    for name in ("mql5_signals", "mql5_forum", "mql5_articles", "mql5_codebase"):
        src = (DESK / "side_channels" / f"{name}.py").read_text(encoding="utf-8")
        assert "BLOCKED_TERMS" not in src and "mql5_terms" not in src, name


# ----------------------------------------------------------------------------- the method fence
def test_a_redirect_into_a_login_wall_is_refused_and_never_followed(server: Any) -> None:
    base, hits = server
    with pytest.raises(pf.MethodRefused) as exc:
        pf.fenced_urlopen(f"{base}/wall", timeout=5)
    assert "login_wall" in str(exc.value.reason)
    assert hits == ["/wall"]                                  # the wall itself was never opened


def test_a_first_url_on_a_login_wall_is_refused_before_a_request(server: Any) -> None:
    base, hits = server
    with pytest.raises(pf.MethodRefused):
        pf.fenced_urlopen(f"{base}/signin", timeout=5)
    assert hits == []


def test_redirects_are_followed_and_kept_visible(server: Any) -> None:
    base, _ = server
    with pf.fenced_urlopen(f"{base}/hop", timeout=5) as fh:
        assert fh.read().startswith(b"<html>")
        assert fh.redirects == [(301, f"{base}/hop", f"{base}/ok")]
    r = pf.get(f"{base}/hop", gate=None, retries=0)
    assert r.ok and r.redirects and r.redirects[0][0] == 301 and r.final_url.endswith("/ok")


def test_the_shared_client_never_retries_a_method_refusal(server: Any) -> None:
    base, hits = server
    r = pf.get(f"{base}/wall", gate=None, retries=3, sleep=lambda _s: None)
    assert not r.ok and r.error.startswith("METHOD_BLOCKED:login_wall")
    assert r.attempts == 1 and hits == ["/wall"]


def test_login_wall_matches_walls_and_not_lookalikes() -> None:
    for url in ("https://x.com/i/flow/login", "https://a.org/accounts/login?next=/",
                "https://a.org/cdn-cgi/challenge-platform/h/b", "https://a.org/sign-in"):
        assert pf.login_wall(url), url
    for url in ("https://a.org/blog/login-trends-2026", "https://www.mql5.com/en/signals/1",
                "https://a.org/data.csv"):
        assert not pf.login_wall(url), url


def test_a_compressed_body_is_inflated_only_up_to_the_cap() -> None:
    bomb = gzip.compress(b"\0" * 5_000_000)
    assert len(pf.inflate(bomb, "gzip", cap=1000)) == 1000
    assert pf.inflate(bomb, "gzip") == b"\0" * 5_000_000
    assert pf.inflate(b"plain", "") == b"plain"


@pytest.mark.parametrize("path", CALL_SITES)
def test_every_named_call_site_goes_through_the_fenced_door(path: str) -> None:
    src = (ROOT / path).read_text(encoding="utf-8")
    assert "fenced_urlopen" in src, path
    bare = [ln for ln in src.splitlines()
            if ("urlopen(" in ln and "fenced_urlopen" not in ln)
            or "requests.get(" in ln or "requests.Session(" in ln]
    assert bare == [], (path, bare)
