"""The regional hunters' access gate: a refusal stands, robots.txt is read first, nobody logs in.

Offline. `_raw_get` is replaced, so what is pinned is the gate's behaviour, never a live venue.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "side_channels"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import regional_survivor_hunters as rh  # noqa: E402

from libs.data.robots_gate import RobotsGate, robots_allows, robots_rules  # noqa: E402

SPEC = ("X", "en", "A", lambda p: f"https://a.example/list?page={p}", r"nomatch",
        "https://a.example", 3)


def _wire(monkeypatch, pages: dict[str, tuple[int | None, str]]) -> list[str]:
    calls: list[str] = []

    def raw(url: str, timeout: float = 0, accept_json: bool = False):
        calls.append(url)
        code, body = pages.get(url, (404, ""))
        return code, body, ""

    monkeypatch.setattr(rh, "_raw_get", raw)
    monkeypatch.setitem(rh._GATE, "gate", rh.AccessGate())
    monkeypatch.setitem(rh._DEADLINE, "at", None)
    return calls


def test_robots_rules_wildcards_and_longest_match() -> None:
    rules = robots_rules("User-agent: *\nDisallow: /*/positions/page*\nDisallow: /x$\n"
                         "User-agent: BadBot\nDisallow: /")
    assert robots_allows(rules, "https://h/en/signals/1")
    assert not robots_allows(rules, "https://h/en/signals/1/positions/page2")
    assert not robots_allows(rules, "https://h/x") and robots_allows(rules, "https://h/xy")
    assert robots_allows([("/", False), ("/en/", True)], "https://h/en/a")
    g = RobotsGate(lambda u: (500, ""))
    assert g.check("https://h/a") == "UNREAD"
    assert RobotsGate(lambda u: (404, "")).check("https://h/a") == "ALLOWED"


def test_a_403_stops_the_source_with_no_alternate_and_no_site_root_walk(monkeypatch) -> None:
    monkeypatch.setitem(rh.ALTERNATES, "t", ("https://b.example/list",))
    calls = _wire(monkeypatch, {"https://a.example/list?page=1": (403, ""),
                                "https://b.example/list": (200, "<a>rank</a>")})
    res = rh.mine_source("t", SPEC, 1)
    assert res["state"] == "hard_stop" and res["diagnosis"] == "HARD_STOP"
    assert calls == ["https://a.example/robots.txt", "https://a.example/list?page=1"]
    # the host stays stopped: a second URL on it is not fetched at all
    with pytest.raises(rh.FetchError, match="HARD_STOPPED"):
        rh.fetch("https://a.example/other")
    assert len(calls) == 2
    assert rh.gate().stops["a.example"]["code"] == 403


def test_a_stop_expires_into_one_reprobe_after_the_cooldown() -> None:
    old = (datetime.now(tz=UTC) - timedelta(hours=rh.HARD_STOP_COOLDOWN_H + 1)).isoformat()
    g = rh.AccessGate({"a.example": {"code": 403, "at": old},
                       "b.example": {"code": 429, "at": datetime.now(tz=UTC).isoformat()}})
    assert not g.stopped("a.example") and g.stopped("b.example")


def test_robots_disallow_and_unreadable_robots_are_not_fetched(monkeypatch) -> None:
    calls = _wire(monkeypatch, {
        "https://a.example/robots.txt": (200, "User-agent: *\nDisallow: /list"),
        "https://c.example/robots.txt": (503, "")})
    with pytest.raises(rh.FetchError, match="ROBOTS_DISALLOWED"):
        rh.fetch("https://a.example/list?page=1")
    with pytest.raises(rh.FetchError, match="ROBOTS_UNREAD"):
        rh.fetch("https://c.example/list")
    assert calls == ["https://a.example/robots.txt", "https://c.example/robots.txt"]
    assert rh.gate().counts == {"robots_disallowed": 1, "robots_unread": 1}


def test_a_login_wall_is_blocked_auth_and_ends_the_walk(monkeypatch) -> None:
    calls = _wire(monkeypatch, {"https://a.example/list?page=1":
                                (200, "<h1>Log in to your Profile</h1>")})
    res = rh.mine_source("t", SPEC, 1)
    assert res["state"] == "blocked_auth"
    assert "https://a.example/" not in calls           # no site-root exploration past a login


def test_terms_and_login_rows_bar_a_ground_before_any_fetch(monkeypatch) -> None:
    calls = _wire(monkeypatch, {})
    rows = {"f": {"terms": "FORBIDS", "terms_evidence": "no automated access"},
            "l": {"auth": "LOGIN_REQUIRED"}, "u": {"terms": "UNREAD"}}
    monkeypatch.setattr(rh, "access_rows", lambda: rows)
    assert rh.access_bar("f")[0] == "terms_forbid"
    assert rh.access_bar("l")[0] == "blocked_auth"
    assert rh.access_bar("u") == ("", "") and rh.access_bar("absent") == ("", "")
    work = rh._work_source("f", SPEC, {})
    assert work["pages"][0]["state"] == "terms_forbid" and calls == []


def test_the_committed_rows_cover_every_ground_and_bar_the_login_only_one() -> None:
    rows = rh.access_rows()
    assert set(rh.SOURCES) | {"fbs_tape"} <= set(rows)
    assert rh.access_bar("octa_masters", rows)[0] == "blocked_auth"


def test_requests_say_who_we_are_and_never_retry() -> None:
    assert rh.HEADERS["User-Agent"].startswith("quant-research/")
    import inspect
    src = inspect.getsource(rh._raw_get)
    assert "retries=0" in src and "Referer" not in inspect.getsource(rh.fetch)


def test_the_suite_runs_the_hunters_inside_its_own_timeout() -> None:
    import run_all_miners as ram
    assert ("regional_survivors", ram.regional_survivors_mine) in ram.ALL_MINERS
