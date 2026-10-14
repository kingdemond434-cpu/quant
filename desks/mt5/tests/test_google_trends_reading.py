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
    class Resp:
        status_code = status
        text = ""

    Resp.headers = headers or {}

    def get(url: str, **_k: object) -> object:
        calls.append(url)
        return Resp()
    return get


@pytest.mark.parametrize(("status", "headers", "wait"), [
    (429, {"Retry-After": "120"}, 120.0),
    (403, None, 3600.0),
])
def test_a_refusal_stops_the_pass_and_the_next_pass_requests_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int, headers: dict | None,
        wait: float) -> None:
    monkeypatch.setattr(gtm, "BLOCK_STATE", tmp_path / "block.json")
    reg = tmp_path / "blocked_sources.json"
    reg.write_text(json.dumps({"note": "n", "sources": {"other": {"diagnosis": "X"}}}))
    monkeypatch.setattr(gtm, "BLOCKED_REGISTER", reg)
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _refuse(calls, status, headers))
    assert gtm.mine_google_trends(now=NOW) == []
    assert len(calls) == 1                                    # exactly one request
    blk = gtm.LAST_PASS["block"]
    assert gtm.LAST_PASS["status"] == "METHOD_BLOCKED" and blk["http_status"] == status
    assert blk["backoff_s"] == wait
    doc = json.loads(reg.read_text())
    assert "other" in doc["sources"]
    assert doc["sources"][gtm.REGISTER_KEY]["diagnosis"] == "METHOD_BLOCKED"
    calls.clear()
    assert gtm.mine_google_trends(now=NOW + timedelta(seconds=wait - 1)) == []
    assert calls == [] and gtm.LAST_PASS["skipped"] is True   # none in the next pass


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
    monkeypatch.setattr(gtm.hard_stop, "record_block", boom)
    calls: list[str] = []
    monkeypatch.setattr(gtm.requests, "get", _refuse(calls, 429))
    assert gtm.mine_google_trends(now=NOW) == []
    assert len(calls) == 1
    assert gtm.LAST_PASS["status"] == "METHOD_BLOCKED" and "disk full" in gtm.LAST_PASS[
        "persist_error"]
