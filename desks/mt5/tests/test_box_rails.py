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
