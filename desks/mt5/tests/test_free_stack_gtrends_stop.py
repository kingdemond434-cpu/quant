"""The free_stack gtrends route under the hard stop, robots, and an honest User-Agent
(audit 0b66b08de MF2 + MF5). Every fetch is a fake: no network, no tracked file touched."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from desks.mt5.research import hard_stop as _hs  # noqa: E402

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


def _merge(cursor: dict, h: fs.Harvest) -> dict:
    """What the hunter does with a harvest's cursor between passes."""
    return {**cursor, **h.cursor}


def test_a_429_is_one_request_then_a_hold_no_timer_releases(_register: Path) -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls), ROW, {}, NOW)
    api = [u for u, _ua in calls if not u.endswith("/robots.txt")]
    assert len(api) == 1                                 # the 429, and not one request more
    assert h.status == "METHOD_BLOCKED" and h.requests == len(calls) == 2
    rec = h.cursor["hold"]
    assert (rec["key"], rec["verdict"], rec["status"], rec["released_by"]) == (
        "site:trends.google.com", "HARD_STOP", 429, None)
    doc = json.loads(_register.read_text("utf-8"))
    assert doc["holds"]["site:trends.google.com"]["released_by"] is None
    assert doc["sources"]["free_stack_gtrends"]["diagnosis"] == "HARD_STOP"
    cursor = _merge({}, h)
    for later in (timedelta(hours=25), timedelta(days=11), timedelta(days=400)):
        calls2: list[tuple[str, str]] = []
        h2 = fs.fetch_gtrends(_fake(calls2, api=200), ROW, cursor, NOW + later)
        assert calls2 == [] and h2.requests == 0 and h2.status == "METHOD_BLOCKED", later


def test_after_a_release_the_next_pass_fetches_and_history_is_kept(_register: Path) -> None:
    calls: list[tuple[str, str]] = []
    cursor = _merge({}, fs.fetch_gtrends(_fake(calls), ROW, {}, NOW))
    _hs.release(_register, "site:trends.google.com", "tester", now=NOW + timedelta(days=2))
    calls2: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls2, api=429), ROW, cursor, NOW + timedelta(days=3))
    assert [u for u, _ in calls2 if not u.endswith("/robots.txt")]        # it fetched
    assert h.cursor["hold"]["held_at"] == (NOW + timedelta(days=3)).timestamp()
    doc = json.loads(_register.read_text("utf-8"))
    assert [r["released_by"] for r in doc["hold_history"]] == ["tester"]
    assert doc["holds"]["site:trends.google.com"]["released_by"] is None


@pytest.mark.parametrize("code", [401, 403])
def test_a_401_or_403_stops_on_the_first_one_too(code: int) -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, api=code), ROW, {}, NOW)
    assert len([u for u, _ in calls if not u.endswith("/robots.txt")]) == 1
    assert h.cursor["hold"]["status"] == code


def test_a_5xx_is_not_a_hold() -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, api=503), ROW, {}, NOW)
    assert "hold" not in h.cursor and h.status == "BLOCKED"
    assert len(calls) == 1 + len(ROW["terms"])


def test_the_header_sent_is_the_desks_one_string_never_a_browser() -> None:
    calls: list[tuple[str, str]] = []
    fs.fetch_gtrends(_fake(calls), ROW, {}, NOW)
    assert calls and all(ua == fs.GTRENDS_UA for _u, ua in calls)   # robots read under it too
    assert fs.GTRENDS_UA is _hs.DESK_UA
    assert not any(m in fs.GTRENDS_UA.lower() for m in BROWSER_MARKERS)


def test_a_robots_disallow_is_not_fetched_and_robots_is_kept_a_day() -> None:
    calls: list[tuple[str, str]] = []
    robots = (b"User-agent: *\nAllow: /\n\nUser-agent: " + _hs.DESK_UA_PRODUCT.encode()
              + b"\nDisallow: /trends/api/\n")
    h = fs.fetch_gtrends(_fake(calls, robots=robots), ROW, {}, NOW)
    assert [u for u, _ in calls] == ["https://trends.google.com/robots.txt"]
    assert h.status == "ROBOTS_DISALLOWED" and "hold" not in h.cursor
    cursor = _merge({}, h)
    calls2: list[tuple[str, str]] = []
    fs.fetch_gtrends(_fake(calls2, robots=robots), ROW, cursor, NOW + timedelta(hours=23))
    assert calls2 == []                                   # kept a day: not re-read
    calls3: list[tuple[str, str]] = []
    fs.fetch_gtrends(_fake(calls3, robots=b"User-agent: *\nAllow: /\n", api=500), ROW, cursor,
                     NOW + timedelta(hours=25))
    assert calls3[0][0] == "https://trends.google.com/robots.txt" and len(calls3) > 1


@pytest.mark.parametrize("code,fetched", [(503, False), (404, True)])
def test_a_5xx_robots_stops_the_pass_and_a_404_robots_allows(code: int, fetched: bool) -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, robots=code, api=500), ROW, {}, NOW)
    api = [u for u, _ in calls if not u.endswith("/robots.txt")]
    assert bool(api) is fetched
    if not fetched:
        assert h.status == "ROBOTS_UNAVAILABLE" and "hold" not in h.cursor
        assert "robots" not in h.cursor or not h.cursor["robots"]    # re-read next pass


def test_a_403_on_robots_itself_is_a_person_hold() -> None:
    calls: list[tuple[str, str]] = []
    h = fs.fetch_gtrends(_fake(calls, robots=403), ROW, {}, NOW)
    assert len(calls) == 1 and h.cursor["hold"]["verdict"] == "ROBOTS_HOLD"
    calls2: list[tuple[str, str]] = []
    fs.fetch_gtrends(_fake(calls2), ROW, _merge({}, h), NOW + timedelta(days=11))
    assert calls2 == []


def test_the_release_cli_names_the_person_and_keeps_the_record(tmp_path: Path) -> None:
    reg = tmp_path / "reg.json"
    rec = _hs.hold_record("HARD_STOP", 429, "https://trends.google.com/trends/api/x", NOW)
    _hs.place_hold(rec, reg, source_key="free_stack_gtrends")
    assert _hs.main(["--register", str(reg), "--release", rec["key"]]) == 2   # no --by: refused
    assert _hs.active_hold(reg, [rec["key"]]) is not None
    assert _hs.main(["--register", str(reg), "--release", rec["key"], "--by", "desk-operator"]) == 0
    row = json.loads(reg.read_text("utf-8"))["holds"][rec["key"]]
    assert row["released_by"] == "desk-operator" and row["released_at"] is not None
    assert row["held_at"] == rec["held_at"] and row["status"] == 429      # the record is kept
    assert _hs.active_hold(reg, [rec["key"]]) is None


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_blank_released_by_releases_nothing(tmp_path: Path, blank: str) -> None:
    """A hold is released only by a NAMED person (audit b323f23a9 MF1): an empty or whitespace
    `released_by`, on the register row or in its history, leaves the hold in force."""
    reg = tmp_path / "blocked_sources.json"
    rec = _hs.hold_record(_hs.VERDICT_HARD_STOP, 429, "https://trends.google.com/x", NOW)
    _hs.place_hold(rec, reg)
    data = json.loads(reg.read_text("utf-8"))
    data["holds"][rec["key"]].update(released_by=blank, released_at=NOW.timestamp() + 60)
    data["hold_history"] = [{**rec, "released_by": blank, "released_at": NOW.timestamp() + 60}]
    reg.write_text(json.dumps(data), "utf-8")
    assert _hs.active_hold(reg, [rec["key"]]) is not None
    assert _hs.active_hold(reg, [], mirror=rec) is not None
    with pytest.raises(ValueError):
        _hs.release(reg, rec["key"], blank)
    _hs.release(reg, rec["key"], "zuck", now=NOW + timedelta(minutes=2))
    assert _hs.active_hold(reg, [rec["key"]]) is None
