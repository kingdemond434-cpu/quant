"""Pass-6 lanes audit a7698187e (HOLD): the findings, on fixtures and a LOCAL server, no network.

MF1 `_Run.page()` / `index_page()` follow redirects BY HAND: every hop is checked against the
    run's holds, the method fence and (cross-origin) its own robots.txt BEFORE it is requested,
    and a 401/403/429 holds the site that REFUSED, never the first URL's (1-hop and 2-hop).
MF2 an IPv6 hold persists as `site:<addr>` and re-seeds as the same address (never "2001").
MF3 a live-input redirect hop that stays inside the first URL's own policy row is followed;
    every cut hop carries (and writes) a missed-growth line.
SF  host aliases (IDN, legacy IPv4, trailing-dot IP, expanded IPv6) share one hold; mirrors of a
    held site (Google cache, archive.today, translate, archive.org/wait) are held; a frontier row
    that is a string or has outcome null is DAMAGED (fail closed); a double- or triple-encoded
    dot-dot stays inside a held folder.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from libs.research import hunt_frontier as hf  # noqa: E402
from research import deep_forest_miner as D  # noqa: E402

BODY = b"<html><body>" + b"gold breakout rule. " * 120 + b"</body></html>"


# ------------------------------------------------------------------ a local two-host server
@pytest.fixture
def srv(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[int, list[tuple[str, str]]]]:
    """One server answering as two sites: 127.0.0.1 and localhost (by the Host header)."""
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)
    hits: list[tuple[str, str]] = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:
            pass

        def _go(self, where: str) -> None:
            self.send_response(302)
            self.send_header("Location", where)
            self.end_headers()

        def do_GET(self) -> None:
            host = str(self.headers.get("Host") or "").split(":")[0]
            hits.append((host, self.path))
            port = self.server.server_address[1]
            other = f"http://localhost:{port}"
            if self.path == "/robots.txt":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"User-agent: *\nDisallow: /private\n")
                return
            routes = {"/one": f"{other}/t", "/two": "/two-b", "/two-b": f"{other}/t",
                      "/one403": f"{other}/403", "/two403": "/two403-b",
                      "/two403-b": f"{other}/403", "/priv": f"{other}/private"}
            if host != "localhost" and self.path in routes:
                self._go(routes[self.path])
                return
            if self.path == "/403":
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(BODY)

    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1], hits
    s.shutdown()
    s.server_close()


def _run() -> Any:
    r = D._Run(60.0, True, None, None)
    r.ground = {"name": "g"}
    return r


@pytest.mark.parametrize("path", ["/one", "/two"])
@pytest.mark.parametrize("route", ["page", "index_page"])
def test_mf1_redirect_into_a_held_site_sends_it_no_request(srv: Any, path: str,
                                                           route: str) -> None:
    port, hits = srv
    r = _run()
    r.holds.hold(f"http://localhost:{port}/", 403)
    assert getattr(r, route)(f"http://127.0.0.1:{port}{path}") == ""
    assert not [h for h in hits if h[0] == "localhost"], hits     # not even its robots.txt
    assert any(s.get("redirect_stopped") for s in r.status)


@pytest.mark.parametrize("path", ["/one403", "/two403"])
@pytest.mark.parametrize("route", ["page", "index_page"])
def test_mf1_a_refusal_at_the_redirect_target_holds_the_refusing_site(
        srv: Any, path: str, route: str) -> None:
    port, _ = srv
    r = _run()
    assert getattr(r, route)(f"http://127.0.0.1:{port}{path}") == ""
    assert "localhost" in r.holds.sites and "127.0.0.1" not in r.holds.sites, r.holds.sites
    assert r.ground_holds == ["localhost"]


def test_mf1_a_cross_origin_hop_obeys_the_target_robots(srv: Any) -> None:
    port, hits = srv
    r = _run()
    assert r.page(f"http://127.0.0.1:{port}/priv") == ""
    assert ("localhost", "/robots.txt") in hits and ("localhost", "/private") not in hits


def test_mf1_an_unheld_redirect_still_reads_the_page(srv: Any) -> None:
    port, _ = srv
    r = _run()
    assert "gold breakout" in r.page(f"http://127.0.0.1:{port}/two")


# ------------------------------------------------------------------------------- IPv6 (MF2)
def test_mf2_an_ipv6_hold_persists_and_reseeds_as_the_same_address(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fp = tmp_path / "deep_forest_frontier.json"
    monkeypatch.setattr(D, "_frontier_path", lambda: fp)
    r = D._Run(60.0, True, None, None)
    r.holds.hold("http://[2001:db8::1]:8080/x", 403, ground="g")
    assert list(r.holds.sites) == ["2001:db8::1"]
    D._record_frontier([], [], dict(r.holds.sites))
    assert "site:2001:db8::1" in hf.load(fp).vectors
    r2 = D._Run(60.0, True, None, None)
    D.seed_persisted_holds(r2, [{"name": "g", "site": "u.org"}], hf.load(fp))
    assert list(r2.holds.sites) == ["2001:db8::1"]
    assert r2.holds.held("http://[2001:DB8:0::1]/y")
    assert D._refusing_domain("ACCESS_REFUSED: HTTP 403 from [2001:db8::1]: x") == "2001:db8::1"
    assert D.url_host("2001:db8::1") == "[2001:db8::1]"
    assert D.robots_origin("http://[2001:db8::1]:81/a") == "http://[2001:db8::1]:81"


# -------------------------------------------------------------------- host aliases (SF)
@pytest.mark.parametrize(("held", "alias"), [
    ("https://xn--r8jz45g.jp/", "https://例え.jp/"),
    ("https://例え.jp/", "https://XN--R8JZ45G.jp/"),
    ("http://192.168.1.1/", "http://3232235777/"),
    ("http://192.168.1.1/", "http://0xC0A80101/"),
    ("http://192.168.1.1/", "http://0300.0250.1.1/"),
    ("http://192.168.1.1/", "http://192.168.257/"),
    ("http://10.0.0.1/", "http://10.1/"),
    ("http://192.168.1.1/", "http://192.168.1.1./"),
    ("http://[2001:db8::1]/", "http://[2001:0db8:0000::0:1]/"),
])
def test_sf_alias_spellings_share_one_hold(held: str, alias: str) -> None:
    s = D.SiteHolds()
    s.hold(held, 403)
    assert s.held(alias)


def test_sf_a_trailing_dot_ip_is_keyed_whole_never_by_its_last_labels() -> None:
    assert D.registrable_domain("http://192.168.1.1./") == "192.168.1.1"
    s = D.SiteHolds()
    s.hold("http://192.168.1.1./", 403)
    assert list(s.sites) == ["192.168.1.1"] and not s.held("http://10.0.1.1/")
    assert D.registrable_domain("api.1.example") == "1.example"      # a name, not an IP


# ----------------------------------------------------------------------- mirrors (SF)
MIRRORS = ["https://webcache.googleusercontent.com/search?q=cache:held.example.com/p",
           "https://webcache.googleusercontent.com/search?q=cache:AbCdEf12:https://held.example.com/p",
           "https://archive.ph/newest/https://held.example.com/p",
           "https://archive.today/2020/https://held.example.com/p",
           "https://archive.is/https://held.example.com/p",
           "https://translate.google.com/translate?u=https://held.example.com/p",
           "https://held-example-com.translate.goog/p",
           "http://archive.org/wait/https://held.example.com/p",
           "https://web.archive.org/web/https://held.example.com/p",
           "https://web.archive.org/web/2019/https://www.held.example.com/p"]


@pytest.mark.parametrize("u", MIRRORS)
def test_sf_mirrors_of_a_held_site_are_held(u: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(D.pf, "get", lambda url, **k: sent.append(url))
    r = _run()
    r.holds.hold("https://held.example.com/", 403)
    assert r.held_url(u)
    r.follow(u, "a", via="t")
    assert not r.frontier
    assert r.page(u) == "" and r.index_page(u) == "" and sent == []
    assert r.status[-1]["site_held"] == "example.com"
    r.follow("https://archive.ph/newest/https://ok.example.org/p", "b", via="t")
    assert len(r.frontier) == 1


# ------------------------------------------------------------- damaged frontier rows (SF)
@pytest.mark.parametrize("vectors", [
    {"site:h.example": "BLOCKED"},
    {"site:h.example": {"outcome": None, "blocker": "ACCESS_REFUSED: HTTP 403 from h.example"}},
    {"site:h.example": {"outcome": "SOMETHING", "blocker": "x"}},
    {"site:h.example": {"outcome": "BLOCKED", "blocker": 403}},
    {"site:h.example": {"blocker": "ACCESS_REFUSED: HTTP 403 from h.example"}},
    {"ok": {"first_seen": "2026-01-01"}, "bad": ["BLOCKED"]},
])
def test_sf_a_partly_corrupt_frontier_fails_closed_and_is_kept(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vectors: dict[str, Any]) -> None:
    fp = tmp_path / "f.json"
    text = json.dumps({"vectors": vectors})
    fp.write_text(text, "utf-8")
    monkeypatch.setattr(D, "_frontier_path", lambda: fp)
    assert D.frontier_damaged(fp)
    assert D._record_frontier([], [{"name": "g", "site": "u.org"}])["status"] == "UNMEASURED"
    assert fp.read_text("utf-8") == text


def test_sf_a_legacy_frontier_row_is_still_readable(tmp_path: Path) -> None:
    fp = tmp_path / "f.json"
    fp.write_text(json.dumps({"vectors": {"g": {"first_seen": "2026-01-01"}}}), "utf-8")
    assert not D.frontier_damaged(fp)


# -------------------------------------------------------------------- path decoding (SF)
JPX = "https://www.jpx.co.jp/markets/statistics-equities/short-selling"


@pytest.mark.parametrize("tail", ["/%252e%252e/x.xls", "/%25252e%25252e/x.xls",
                                  "/%2e%2e%252f%2e%2e/x.xls", "/..;x/x.xls", "/..%3Bx/x.xls",
                                  "/..%253Bx/x.xls", "/..%25253Bx/x.xls"])
def test_sf_encoded_dot_dot_stays_inside_the_held_folder(tail: str) -> None:
    assert tf.input_source(JPX + tail) == "jpx_short_selling_ratio"


def test_sf_a_real_dot_dot_still_leaves_the_folder() -> None:
    assert tf.input_source(JPX + "/../x.xls") is None


# ------------------------------------------------------------- live-input redirect hops (MF3)
@pytest.mark.parametrize(("first", "hop"), [
    ("https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
     "https://query2.finance.yahoo.com/v8/finance/chart/GC=F"),
    ("https://www.reddit.com/r/algotrading/hot.json", "https://old.reddit.com/r/algotrading/hot.json"),
])
def test_mf3_a_hop_inside_the_first_urls_own_source_is_followed(first: str, hop: str) -> None:
    h = tf.FencedRedirectHandler(live_input=True)
    new = h.redirect_request(urllib.request.Request(first), None, 302, "F", {}, hop)
    assert new is not None and new.full_url == hop
    assert tf.same_source_hop(first, hop)


def test_mf3_a_hop_into_another_route_is_cut_with_a_missed_growth_line(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "redirect_cuts.jsonl"
    monkeypatch.setenv("QUANT_REDIRECT_CUTS", str(ledger))
    h = tf.FencedRedirectHandler(live_input=True)
    with pytest.raises(tf.TermsFenced) as ei:
        # an open jpx page -> the held short-selling folder: same host, ANOTHER policy row
        h.redirect_request(urllib.request.Request("https://www.jpx.co.jp/markets/"), None, 302,
                           "F", {}, JPX + "/x.xls")
    line = ei.value.missed_growth
    assert line and line["kind"] == "redirect_cut" and line["delta_elogw"] == "UNMEASURED"
    assert line["source"] == "jpx_short_selling_ratio" and "UNMEASURED" in line["cause"]
    # a yahoo chain cannot hop into reddit either: not its own source
    with pytest.raises(tf.TermsFenced) as e2:
        tf.FencedRedirectHandler(live_input=True).redirect_request(
            urllib.request.Request("https://query1.finance.yahoo.com/x"), None, 302, "F", {},
            "https://www.reddit.com/r/x/hot.json")
    assert e2.value.missed_growth and e2.value.missed_growth["source"] == "reddit"
    rows = tf.redirect_cut_lines(str(ledger))
    assert [r["source"] for r in rows] == ["jpx_short_selling_ratio", "reddit"]


def test_mf3_the_fetch_door_cut_writes_its_line_end_to_end(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    ledger = tmp_path / "cuts.jsonl"
    monkeypatch.setenv("QUANT_REDIRECT_CUTS", str(ledger))

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:
            pass

        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", JPX + "/x.xls")
            self.end_headers()
    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        with pytest.raises(tf.TermsFenced):
            tf.guarded_urlopen(f"http://127.0.0.1:{s.server_address[1]}/a", live_hops=True)
    finally:
        s.shutdown()
        s.server_close()
    (row,) = tf.redirect_cut_lines(str(ledger))
    assert row["to"].startswith(JPX) and row["status"] == tf.IDEAS_ONLY


def test_mf3_under_pytest_no_override_writes_no_desk_ledger(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_REDIRECT_CUTS", raising=False)
    assert tf._redirect_cuts_path() is None


# --------------------------------------- delta audit e8bd75903: every cut writes ONE line
@pytest.fixture
def cutsrv(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """127.0.0.1 redirects by path to every kind of hop fetch_hops must cut."""
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setattr(D.time, "sleep", lambda *_: None)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:
            pass

        def do_GET(self) -> None:
            port = self.server.server_address[1]
            if self.path == "/robots.txt":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"User-agent: *\nDisallow: /private\n")
                return
            loc = {"/held": f"http://localhost:{port}/t",
                   "/mirror": f"https://web.archive.org/web/2019/http://localhost:{port}/t",
                   "/alias": "http://2130706434/t",
                   "/upper": f"HTTP://LOCALHOST:{port}/t",
                   "/fenced": "https://nitter.net/x",
                   "/wall": "/login",
                   "/xpriv": f"http://localhost:{port}/private",
                   "/spriv": "/private",
                   "/unread": "http://127.0.0.1:1/x",
                   "/loop": "/loop",
                   "/ftp": "ftp://files.example.org/x"}.get(self.path)
            if loc is not None:
                self.send_response(302)
                self.send_header("Location", loc)
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(BODY)
    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]
    s.shutdown()
    s.server_close()


CUT_KINDS = [("/held", "site_held"), ("/mirror", "site_held"), ("/alias", "site_held"),
             ("/upper", "site_held"), ("/fenced", "nitter"), ("/wall", "login_wall"),
             ("/xpriv", "robots"), ("/spriv", "robots"), ("/unread", "robots"),
             ("/loop", "too_many_redirects"), ("/ftp", "non_http_redirect")]


@pytest.mark.parametrize(("path", "kind"), CUT_KINDS)
@pytest.mark.parametrize("route", ["page", "index_page"])
def test_delta_every_cut_hop_writes_exactly_one_missed_growth_line(
        cutsrv: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, kind: str,
        route: str) -> None:
    ledger = tmp_path / "cuts.jsonl"
    monkeypatch.setenv("QUANT_REDIRECT_CUTS", str(ledger))
    r = _run()
    if kind == "site_held":
        r.holds.hold(f"http://localhost:{cutsrv}/", 403)
        r.holds.hold("http://127.0.0.2/", 403)
    assert getattr(r, route)(f"http://127.0.0.1:{cutsrv}{path}") == ""
    rows = tf.redirect_cut_lines(str(ledger))
    assert len(rows) == 1, rows
    assert rows[0]["source"] == kind and rows[0]["delta_elogw"] == "UNMEASURED"
    (st,) = [x for x in r.status if x.get("redirect_stopped")]
    assert st["missed_growth"]["kind"] == "redirect_cut" and st["missed_growth"]["source"] == kind


def test_delta_a_same_origin_hop_into_a_disallowed_path_is_not_requested(cutsrv: int) -> None:
    r = _run()
    assert r.page(f"http://127.0.0.1:{cutsrv}/spriv") == ""
    assert [x for x in r.status if x.get("redirect_stopped", "").endswith("/private")]


def test_delta_an_ipv4_mapped_address_shares_the_ipv4_hold() -> None:
    assert D.canonical_host("::ffff:192.168.1.1") == "192.168.1.1"
    s = D.SiteHolds()
    s.hold("http://192.168.1.1/", 403)
    assert s.held("http://[::ffff:192.168.1.1]/x") and s.held("http://[::FFFF:c0a8:101]/")
    s2 = D.SiteHolds()
    s2.hold("http://[::ffff:10.0.0.1]/", 403)
    assert s2.held("http://10.0.0.1/")


def test_delta_a_non_utf8_frontier_is_damaged_and_kept(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fp = tmp_path / "f.json"
    raw = b'{"vectors": {"site:h.example": {"outcome": "BLOCKED", "blocker": "\xff\xfe"}}}'
    fp.write_bytes(raw)
    monkeypatch.setattr(D, "_frontier_path", lambda: fp)
    assert D.frontier_damaged(fp)
    assert D._record_frontier([], [{"name": "g", "site": "u.org"}])["status"] == "UNMEASURED"
    assert fp.read_bytes() == raw
