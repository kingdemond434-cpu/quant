"""google_trends_miner: an unmeasurable trend emits no row, never a trend_pct of 0."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import google_trends_miner as gtm  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test touches the box's own hold copy, robots cache or the tracked register."""
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    monkeypatch.setattr(gtm, "ROBOTS_STATE", tmp_path / "robots.json")
    monkeypatch.setattr(gtm, "BLOCKED_REGISTER", tmp_path / "blocked_sources.json")


def _tl(vals: list[float]) -> list[dict]:
    return [{"value": [v]} for v in vals]


def test_short_or_zero_based_timelines_are_unmeasured() -> None:
    assert gtm.trend_reading(_tl([10, 20, 30])) is None
    assert gtm.trend_reading(_tl([0, 0, 0, 0, 5, 5, 5, 5])) is None
    assert gtm.trend_reading(_tl([10, 10, 10, 10, 15, 15, 15, 15])) == pytest.approx(50.0)


def test_the_miner_emits_nothing_for_an_unmeasurable_term(monkeypatch: pytest.MonkeyPatch,
                                                          tmp_path: Path) -> None:
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    class Resp:
        status_code = 200
        text = '"timelineData": ' + json.dumps(_tl([40, 50, 60]))

    monkeypatch.setattr(gtm.requests, "get", lambda *a, **k: Resp())
    assert gtm.mine_google_trends() == []

    class Long(Resp):
        text = '"timelineData": ' + json.dumps(_tl([10, 10, 10, 10, 20, 20, 20, 20]))

    monkeypatch.setattr(gtm.requests, "get", lambda *a, **k: Long())
    rows = gtm.mine_google_trends()
    assert rows and all(r["trend_pct"] == 100.0 for r in rows)


def test_the_embedded_timeline_decodes_whole() -> None:
    page = 'x "timelineData": [{"value": [3]}, {"value": [4]}], "other": [1]'
    assert gtm.timeline_from(page) == [{"value": [3]}, {"value": [4]}]
    assert gtm.timeline_from("nothing here") == []


# ------------------------------------------------------------------------------- the hard stop


NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


def _refuse(calls: list[str], status: int, headers: dict | None = None):
    """Every URL answers `status`, except robots.txt, which answers 404 (no file: unrestricted)
    and is not counted in `calls`; the robots reads are pinned by the robots tests below."""
    class Resp:
        status_code = status
        text = ""

    class NoRobots:
        status_code = 404
        text = ""

    Resp.headers = headers or {}

    def get(url: str, **_k: object) -> object:
        if url.endswith("/robots.txt"):
            return NoRobots()
        calls.append(url)
        return Resp()
    return get


class _Answer:
    status_code = 200
    text = '"timelineData": ' + json.dumps([{"value": [v]} for v in (10, 10, 10, 10, 20, 20,
                                                                         20, 20)])


@pytest.mark.parametrize(("status", "headers"), [(429, {"Retry-After": "120"}), (403, None)])
def test_a_refusal_holds_until_a_person_releases_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int,
        headers: dict | None) -> None:
    """One request, then a hold that NO TIMER releases: passes at +25h, +11d and +400d each send
    0 requests. Retry-After is recorded and releases nothing. A person's release lets the next
    pass fetch, and the released hold is kept in the register's history."""
    reg = tmp_path / "blocked_sources.json"
    reg.write_text(json.dumps({"note": "n", "sources": {"other": {"diagnosis": "X"}}}))
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _refuse(calls, status, headers))
    assert gtm.mine_google_trends(now=NOW) == []
    assert len(calls) == 1                                    # exactly one request
    blk = gtm.LAST_PASS["block"]
    assert gtm.LAST_PASS["status"] == "METHOD_BLOCKED"
    assert (blk["key"], blk["verdict"], blk["status"], blk["released_by"]) == (
        "site:trends.google.com", "HARD_STOP", status, None)
    assert "until" not in blk and "backoff_s" not in blk
    if headers:
        assert gtm.LAST_PASS["retry_after_s"] == 120.0
    doc = json.loads(reg.read_text())
    assert "other" in doc["sources"]
    assert doc["sources"][gtm.REGISTER_KEY]["diagnosis"] == "HARD_STOP"
    assert doc["holds"]["site:trends.google.com"]["released_by"] is None
    for later in (timedelta(hours=25), timedelta(days=11), timedelta(days=400)):
        calls.clear()
        monkeypatch.setattr(gtm.requests, "get", _refuse(calls, 200))
        assert gtm.mine_google_trends(now=NOW + later) == []
        assert calls == [] and gtm.LAST_PASS["skipped"] is True, later

    gtm.hard_stop.release(reg, "site:trends.google.com", "tester",
                          now=NOW + timedelta(days=400, hours=1))
    answered: list[str] = []

    def answer(url: str, **_k: object) -> object:
        answered.append(url)
        return _Answer()
    monkeypatch.setattr(gtm.requests, "get", answer)
    rows = gtm.mine_google_trends(now=NOW + timedelta(days=401))
    assert rows and gtm.LAST_PASS["status"] == "FETCHED" and len(answered) > 1
    assert not gtm.BLOCK_STATE.exists()                       # the released copy is spent
    # a second refusal: a new hold, the released one kept in history
    calls.clear()
    monkeypatch.setattr(gtm.requests, "get", _refuse(calls, status, headers))
    gtm.mine_google_trends(now=NOW + timedelta(days=402))
    doc = json.loads(reg.read_text())
    assert doc["holds"]["site:trends.google.com"]["released_by"] is None
    assert [h["released_by"] for h in doc["hold_history"]] == ["tester"]


def test_a_free_stack_hold_on_the_same_host_holds_this_miner_too(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rec = gtm.hard_stop.hold_record("HARD_STOP", 429, "https://trends.google.com/trends/api/x",
                                    NOW)
    gtm.hard_stop.place_hold(rec, tmp_path / "blocked_sources.json",
                             source_key="free_stack_gtrends")
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _refuse(calls, 200))
    gtm.mine_google_trends(now=NOW + timedelta(days=3))
    assert calls == [] and gtm.LAST_PASS["skipped"] is True


def test_a_401_reads_needs_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    monkeypatch.setattr(gtm, "BLOCKED_REGISTER", tmp_path / "r.json")
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _refuse(calls, 401))
    gtm.mine_google_trends(now=NOW)
    assert len(calls) == 1 and gtm.LAST_PASS["status"] == "NEEDS_KEY"


# ------------------------------------------------------------------------------- audit 2b4cd0942

def test_a_point_without_a_value_is_unmeasured_never_zero() -> None:
    tl = _tl([10, 10, 10, 10, 20, 20, 20, 20])
    del tl[5]["value"]
    assert gtm.point_value({"value": [7]}) == 7.0
    assert gtm.point_value({}) is None and gtm.point_value({"value": []}) is None
    assert gtm.trend_reading(tl) is None


def test_the_trailing_partial_week_is_not_a_reading() -> None:
    tl = [*_tl([10, 10, 10, 10, 20, 20, 20, 20]), {"value": [99], "isPartial": True}]
    assert gtm.trend_reading(tl) == pytest.approx(100.0)


def test_a_200_with_no_timeline_is_not_fetched_and_the_desk_ua_is_sent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    seen_ua: list[str] = []

    class Empty:
        status_code = 200
        text = "<html>consent wall</html>"

    def get(url: str, headers: dict | None = None, **_k: object) -> object:
        seen_ua.append((headers or {}).get("User-Agent", ""))
        return Empty()
    monkeypatch.setattr(gtm.requests, "get", get)
    assert gtm.mine_google_trends(now=NOW) == []
    assert gtm.LAST_PASS["status"] == "FAILED" and gtm.LAST_PASS["timelines_read"] == 0
    assert seen_ua and set(seen_ua) == {gtm.DESK_UA} and "Mozilla" not in gtm.DESK_UA


def test_a_refusal_whose_record_cannot_be_written_still_ends_the_pass(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MF4a: persisting the marker raised inside the loop's broad except and the pass kept
    fetching (20 requests after a 429). `blocked` is set and the loop broken first."""
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    monkeypatch.setattr(gtm, "BLOCKED_REGISTER", tmp_path / "r.json")

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")
    monkeypatch.setattr(gtm.hard_stop, "place_hold", boom)
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _refuse(calls, 429))
    assert gtm.mine_google_trends(now=NOW) == []
    assert len(calls) == 1
    assert gtm.LAST_PASS["status"] == "METHOD_BLOCKED" and "disk full" in gtm.LAST_PASS[
        "persist_error"]


# ------------------------------------------------------------------------------- audit 0b66b08de

def test_a_nan_point_is_unmeasured_never_a_number() -> None:
    assert gtm.point_value({"value": [float("nan")]}) is None
    assert gtm.point_value({"value": [float("inf")]}) is None
    assert gtm.point_value({"value": ["nan"]}) is None


def _robots_site(calls: list[str], robots_status: int, robots_text: str):
    class Robots:
        status_code = robots_status
        text = robots_text

    class Page:
        status_code = 200
        text = "<html>no timeline</html>"

    def get(url: str, headers: dict | None = None, **_k: object) -> object:
        calls.append(url)
        assert (headers or {}).get("User-Agent") == gtm.DESK_UA     # robots read under our UA
        return Robots() if url.endswith("/robots.txt") else Page()
    return get


def test_a_robots_disallow_is_not_fetched_and_robots_is_reread_daily(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ROBOTS (principal's scope rule 2026-10-13): a path the group naming the desk's product
    disallows is never requested. It is not a person hold: robots.txt is kept a day, then
    re-read, which is how a site's change of mind is picked up."""
    text = ("User-agent: *\nAllow: /\n\nUser-agent: " + gtm.hard_stop.DESK_UA_PRODUCT
            + "\nDisallow: /trends/explore\n")
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _robots_site(calls, 200, text))
    assert gtm.mine_google_trends(now=NOW) == []
    assert calls == ["https://trends.google.com/robots.txt"]
    assert gtm.LAST_PASS["status"] == "ROBOTS_DISALLOWED"
    assert gtm.LAST_PASS["robots"]["state"] == "DISALLOWED"
    assert not json.loads(gtm.BLOCKED_REGISTER.read_text()).get("holds")   # not a hold
    calls.clear()
    gtm.mine_google_trends(now=NOW + timedelta(hours=23))
    assert calls == []                                            # robots kept a day
    monkeypatch.setattr(gtm.requests, "get",
                        _robots_site(calls, 200, "User-agent: *\nAllow: /\n"))
    gtm.mine_google_trends(now=NOW + timedelta(hours=25))
    assert calls[0] == "https://trends.google.com/robots.txt" and len(calls) > 1


def test_a_5xx_robots_means_no_fetch_this_pass_and_a_reread_next_pass(
        monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _robots_site(calls, 503, ""))
    gtm.mine_google_trends(now=NOW)
    assert calls == ["https://trends.google.com/robots.txt"]
    assert gtm.LAST_PASS["status"] == "ROBOTS_UNAVAILABLE" and not gtm.BLOCK_STATE.exists()
    calls.clear()
    gtm.mine_google_trends(now=NOW + timedelta(minutes=5))
    assert calls == ["https://trends.google.com/robots.txt"]       # re-read, no hold


@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_refusal_on_robots_itself_is_a_person_hold(monkeypatch: pytest.MonkeyPatch,
                                                     status: int) -> None:
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _robots_site(calls, status, ""))
    gtm.mine_google_trends(now=NOW)
    assert calls == ["https://trends.google.com/robots.txt"]
    assert gtm.LAST_PASS["block"]["verdict"] == "ROBOTS_HOLD"
    calls.clear()
    gtm.mine_google_trends(now=NOW + timedelta(days=11))
    assert calls == []


def test_the_ua_is_the_desks_one_string_with_a_contact_path() -> None:
    assert gtm.DESK_UA is gtm.hard_stop.DESK_UA
    assert gtm.DESK_UA.startswith(gtm.hard_stop.DESK_UA_PRODUCT + "/")
    assert "+https://" in gtm.DESK_UA
    assert not any(m in gtm.DESK_UA.lower() for m in ("mozilla", "chrome", "safari", "gecko"))


def test_a_404_robots_allows_and_the_pass_runs(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _robots_site(calls, 404, "not found"))
    gtm.mine_google_trends(now=NOW)
    n_terms = sum(len(t) for t in gtm.SEARCH_TERMS.values())
    assert len(calls) == 1 + n_terms and calls.count("https://trends.google.com/robots.txt") == 1
    assert gtm.LAST_PASS["robots"]["state"] == "ABSENT"
