"""The box's miner clock fetches under data rails (PR #524 audit finding 3, 2026-10-29).

`vps_seat_clock` widens the VPS miners onto the box's own IP. These pin, for that path: every
request carries an honest User-Agent naming the project's research crawler and its public repo
(no browser string, no email); robots.txt is honoured for `*` AND the agent tokens on EVERY
source, with an unreachable robots.txt read as no consent; and no host walled on the VPS
(`seed_miners.SOURCE_WALLS`, pinned here) is ever contacted from the box -- not even its
robots.txt. Nothing here touches the network.
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import requests

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK / "side_channels"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import box_rails  # noqa: E402
import seed_miners  # noqa: E402

#: THE WALLS AS OF 2026-10-29. A wall added or lifted on the VPS must be added or lifted here on
#: purpose: the box must never become the route around one.
PINNED_WALLS: dict[str, str] = {
    "china": "zhihu.com", "investing": "investing.com", "google_trends": "trends.google.com",
    "forexpeacearmy": "forexpeacearmy.com", "myfxbook_outlook": "myfxbook.com",
    "collective2": "collective2.com",
}

ROBOTS = {
    "open.example": (200, "User-agent: *\nDisallow: /private\n"),
    "claude-refused.example": (200, "User-agent: ClaudeBot\nDisallow: /\n\n"
                                    "User-agent: *\nAllow: /\n"),
    "own-refused.example": (200, f"User-agent: {box_rails.AGENT_TOKEN}\nDisallow: /\n"),
    "browser-only.example": (200, "User-agent: Mozilla\nAllow: /\n\n"
                                  "User-agent: *\nDisallow: /\n"),
    "nopolicy.example": (404, ""),
    "forbidden.example": (403, ""),
    "down.example": (503, ""),
    "dead.example": (None, "URLError: timed out"),
}


@pytest.fixture
def rails(monkeypatch):
    """Rails installed over fake transports: what would have gone on the wire is recorded."""
    box_rails._reset_for_tests()
    wire: list[tuple[str, str]] = []
    robots_reads: list[str] = []

    def fake_send(self, request, **kw):
        wire.append((str(request.url), str(request.headers.get("User-Agent"))))
        r = requests.Response()
        r.status_code = 200
        r._content = b"ok"
        r.url = request.url
        return r

    def fake_open(self, req, data=None, timeout=None, **kw):
        ua = req.get_header("User-agent") or ""
        wire.append((req.full_url, ua))
        return "opened"

    def fake_robots(scheme, netloc):
        robots_reads.append(netloc)
        return ROBOTS.get(netloc, (200, ""))

    monkeypatch.setattr(requests.Session, "send", fake_send)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    monkeypatch.setattr(box_rails, "_fetch_robots", fake_robots)
    box_rails.install()
    yield wire, robots_reads
    box_rails._reset_for_tests()


def test_the_walls_are_pinned_and_every_one_is_refused_on_the_box():
    assert set(seed_miners.SOURCE_WALLS) == set(PINNED_WALLS), (
        "SOURCE_WALLS changed: update PINNED_WALLS on purpose")
    hosts = box_rails.walled_hosts()
    for name, host in PINNED_WALLS.items():
        assert host in hosts, name
        assert box_rails.host_walled(seed_miners.SOURCE_WALLS[name]["host"], hosts), name


def test_the_box_never_contacts_a_walled_host_not_even_its_robots(rails):
    wire, robots_reads = rails
    for w in seed_miners.SOURCE_WALLS.values():
        for url in (f"https://{w['host']}/", f"https://{w['host']}/robots.txt",
                    str(w.get("url") or f"https://{w['host']}/x")):
            with pytest.raises(requests.exceptions.ConnectionError):
                requests.get(url, timeout=5)
            with pytest.raises(urllib.error.URLError):
                urllib.request.urlopen(url, timeout=5)
    assert wire == [] and robots_reads == []
    assert all("walled on the VPS" in r["why"] for r in box_rails.refused())


def test_every_request_carries_the_honest_user_agent(rails):
    wire, _ = rails
    requests.get("https://open.example/a", headers={"User-Agent": "Mozilla/5.0 Chrome/126"})
    s = requests.Session()
    s.headers["User-Agent"] = seed_miners.HEADERS["User-Agent"]
    s.get("https://open.example/b")
    urllib.request.urlopen(urllib.request.Request(
        "https://open.example/c", headers={"User-Agent": "Mozilla/5.0"}))
    assert [u for u, _ in wire] == ["https://open.example/a", "https://open.example/b",
                                    "https://open.example/c"]
    for _, ua in wire:
        assert ua == box_rails.USER_AGENT
    ua = box_rails.USER_AGENT
    assert "https://github.com/kingdemond434-cpu/quant" in ua
    assert "Mozilla" not in ua and "Chrome" not in ua and "@" not in ua


@pytest.mark.parametrize("url,allowed", [
    ("https://open.example/page", True),
    ("https://open.example/private/x", False),          # the `*` group
    ("https://claude-refused.example/page", False),     # ClaudeBot named, even though * allows
    ("https://own-refused.example/page", False),        # this crawler's own token named
    ("https://browser-only.example/page", False),       # a browser UA would have passed
    ("https://nopolicy.example/page", True),            # 404 robots = no policy
    ("https://forbidden.example/page", False),          # 403 robots = disallow all
    ("https://down.example/page", False),               # 5xx = not consent
    ("https://dead.example/page", False),               # unreachable = not consent
])
def test_robots_is_honoured_for_every_group_on_every_source(rails, url, allowed):
    wire, _ = rails
    if allowed:
        requests.get(url, timeout=5)
        assert wire and wire[-1][0] == url
    else:
        with pytest.raises(box_rails.RailRefusal):
            requests.get(url, timeout=5)
        with pytest.raises(box_rails.RailRefusal):
            urllib.request.urlopen(url, timeout=5)
        assert wire == []


def test_robots_is_read_once_per_host(rails):
    _, robots_reads = rails
    for i in range(3):
        requests.get(f"https://open.example/{i}", timeout=5)
    assert robots_reads == ["open.example"]


def test_a_redirect_hop_is_checked_too(rails):
    """requests follows redirects through Session.send, so each hop meets the rails."""
    wire, _ = rails
    s = requests.Session()
    req = requests.Request("GET", "https://www.forexpeacearmy.com/forex-reviews").prepare()
    with pytest.raises(box_rails.RailRefusal):
        s.send(req)
    assert wire == []


# ------------------------------------------- PR #524 audit v3: robots.txt redirects, install


@pytest.fixture
def local_site(monkeypatch):
    """A real localhost server; `routes` maps a path to (status, location-or-body)."""
    import http.server
    import threading

    for k in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy",
              "ALL_PROXY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    hits: list[str] = []
    routes: dict[str, tuple[int, str]] = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            code, val = routes.get(self.path, (200, "page"))
            self.send_response(code)
            if 300 <= code < 400:
                self.send_header("Location", val)
                val = ""
            body = val.encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    box_rails._reset_for_tests()
    box_rails.install(walled=frozenset())
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", routes, hits
    finally:
        box_rails._reset_for_tests()
        srv.shutdown()
        srv.server_close()


def test_a_robots_redirect_to_a_non_robots_path_does_not_recurse(local_site):
    base, routes, hits = local_site
    routes["/robots.txt"] = (302, "/login")
    routes["/login"] = (200, "User-agent: *\nDisallow: /private\n")
    with urllib.request.urlopen(f"{base}/page", timeout=5) as r:      # no RecursionError
        assert r.read() == b"page"
    assert hits == ["/robots.txt", "/login", "/page"]
    with pytest.raises(box_rails.RailRefusal):
        requests.get(f"{base}/private/x", timeout=5)
    assert len(hits) == 3                       # robots read once; the refused URL never sent


def test_a_robots_redirect_loop_stops_after_five_hops_and_is_not_consent(local_site):
    base, routes, hits = local_site
    for i in range(20):
        routes["/robots.txt" if i == 0 else f"/r{i}"] = (302, f"/r{i + 1}")
    with pytest.raises(box_rails.RailRefusal, match="redirects"):
        urllib.request.urlopen(f"{base}/page", timeout=5)
    assert len(hits) <= box_rails.ROBOTS_MAX_HOPS + 1 and "/page" not in hits


def test_a_robots_redirect_onto_a_walled_host_is_never_followed(local_site, monkeypatch):
    base, routes, hits = local_site
    routes["/robots.txt"] = (302, "https://www.forexpeacearmy.com/robots.txt")
    monkeypatch.setitem(box_rails._STATE, "walled", frozenset({"forexpeacearmy.com"}))
    with pytest.raises(box_rails.RailRefusal, match="walled"):
        requests.get(f"{base}/page", timeout=5)
    assert hits == ["/robots.txt"]


def test_install_is_not_marked_done_until_the_patches_are_in(monkeypatch):
    box_rails._reset_for_tests()
    orig_open = urllib.request.OpenerDirector.open
    orig_send = requests.Session.send

    def broken():
        raise RuntimeError("SOURCE_WALLS unreadable")

    monkeypatch.setattr(box_rails, "walled_hosts", broken)
    try:
        with pytest.raises(RuntimeError):
            box_rails.install()
        assert box_rails._STATE["installed"] is False
        assert urllib.request.OpenerDirector.open is orig_open
        assert requests.Session.send is orig_send
        monkeypatch.setattr(box_rails, "walled_hosts", lambda: frozenset())
        box_rails.install()                   # the retry installs, rather than reading done
        assert box_rails._STATE["installed"] is True
        assert urllib.request.OpenerDirector.open is not orig_open
        assert requests.Session.send is not orig_send
    finally:
        box_rails._reset_for_tests()
    assert urllib.request.OpenerDirector.open is orig_open
