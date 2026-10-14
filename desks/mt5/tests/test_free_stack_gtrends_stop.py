"""The free_stack gtrends route under the hard stop, robots, and an honest User-Agent
(audit 0b66b08de MF2 + MF5). Every fetch is a fake: no network, no tracked file touched."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402

NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
ROW = {"id": "gtrends", "kind": "gtrends",
       "terms": [[f"term {i}", ["XAUUSD"]] for i in range(10)]}
OPEN_ROBOTS = b"User-agent: *\nDisallow: /search\n"
BROWSER_MARKERS = ("mozilla", "chrome", "safari", "applewebkit", "gecko")


@pytest.fixture(autouse=True)
def _register(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reg = tmp_path / "blocked_sources.json"
    monkeypatch.setattr(fs, "GTRENDS_REGISTER", reg)
    return reg


def _fake(calls: list[tuple[str, str]], *, robots: bytes | int = OPEN_ROBOTS,
          api: int = 429):
    def fetch(url: str, headers=None, body=None) -> bytes:
        calls.append((url, dict(headers or {}).get("User-Agent", "")))
        if url.endswith("/robots.txt"):
            if isinstance(robots, int):
                raise fs.FetchError(f"http_{robots}", url)
            return robots
        raise fs.FetchError(f"http_{api}", url)
    return fetch


def test_a_429_is_one_request_then_a_stop_and_the_next_pass_sends_nothing(
        _register: Path) -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls), ROW, {}, NOW)
    api = [u for u, _ua in calls if not u.endswith("/robots.txt")]
    assert len(api) == 1                                 # the 429, and not one request more
    assert h.status == "METHOD_BLOCKED" and h.requests == len(calls) == 2
    marker = h.cursor["hard_stop"]
    assert marker["http_status"] == 429 and marker["url_class"] == "explore"
    assert "free_stack_gtrends" in _register.read_text("utf-8")
    # the hunter persists the cursor; the next pass, inside the backoff, sends 0 requests
    calls2: list[tuple[str, str]] = []
    h2 = fs.fetch_gtrends(_fake(calls2), ROW, {"hard_stop": marker}, NOW + timedelta(minutes=5))
    assert calls2 == [] and h2.requests == 0 and h2.status == "METHOD_BLOCKED"


@pytest.mark.parametrize("code", [401, 403])
def test_a_401_or_403_stops_on_the_first_one_too(code: int) -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, api=code), ROW, {}, NOW)
    assert len([u for u, _ in calls if not u.endswith("/robots.txt")]) == 1
    assert h.cursor["hard_stop"]["http_status"] == code


def test_a_5xx_is_not_a_hard_stop() -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, api=503), ROW, {}, NOW)
    assert "hard_stop" not in h.cursor and h.status == "BLOCKED"
    assert len(calls) == 1 + len(ROW["terms"])


def test_the_header_sent_is_the_desks_own_never_a_browser() -> None:
    calls: list[tuple[str, str]] = []
    fs.fetch_gtrends(_fake(calls), ROW, {}, NOW)
    assert calls and all(ua == fs.GTRENDS_UA for _u, ua in calls)   # robots read under it too
    assert not any(m in fs.GTRENDS_UA.lower() for m in BROWSER_MARKERS)


def test_a_robots_disallow_is_not_fetched_and_is_held() -> None:
    calls: list[tuple[str, str]] = []
    robots = (b"User-agent: *\nAllow: /\n\n"
              b"User-agent: quant-desk-free-stack-gtrends\nDisallow: /trends/api/\n")
    h = fs.fetch_gtrends(_fake(calls, robots=robots), ROW, {}, NOW)
    assert [u for u, _ in calls] == ["https://trends.google.com/robots.txt"]
    assert h.status == "ROBOTS_HOLD"
    assert h.cursor["hard_stop"]["robots"]["state"] == "DISALLOWED"


@pytest.mark.parametrize("code,fetched", [(503, False), (404, True)])
def test_a_5xx_robots_holds_and_a_404_robots_allows(code: int, fetched: bool) -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, robots=code, api=500), ROW, {}, NOW)
    api = [u for u, _ in calls if not u.endswith("/robots.txt")]
    assert bool(api) is fetched
    if not fetched:
        assert h.status == "ROBOTS_HOLD" and h.cursor["hard_stop"]["robots"]["state"] == \
            "UNAVAILABLE"


def test_a_403_on_robots_itself_is_a_hold() -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, robots=403), ROW, {}, NOW)
    assert len(calls) == 1 and h.cursor["hard_stop"]["url_class"] == "robots.txt"
