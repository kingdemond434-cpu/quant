"""allocator_trigger: a news re-solve request is a watched source (DATA-19).

`news_event_stream` lodges a SEQUENCED re-solve request in `data/allocator_resolve_request.json`.
Until 2026-10-07 `sources()` watched no news artifact, so the request was consumed by nothing. These
tests pin that a new request fires the same fast solve the other sources fire, that a rewrite of the
SAME request does not, and that nothing here touches the real desk or runs the real solver."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import allocator_trigger as at  # noqa: E402
import news_event_stream as nes  # noqa: E402


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    data, reports = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    reports.mkdir()
    monkeypatch.setattr(at, "ROOT", tmp_path)
    monkeypatch.setattr(at, "DATA", data)
    monkeypatch.setattr(at, "REPORTS", reports)
    monkeypatch.setattr(at, "RESOLVE_REQUEST", data / "allocator_resolve_request.json")
    monkeypatch.setattr(at, "STATE", data / "allocator_trigger_state.json")
    monkeypatch.setattr(at, "LOG", data / "allocator_reactions.jsonl")
    monkeypatch.setattr(at, "ALLOCATION", reports / "pf_allocation.json")
    monkeypatch.setattr(at, "MIN_SOLVE_GAP_S", 0.0)
    solves: list[float] = []

    def fake_solve(budget_s: float) -> dict[str, Any]:
        solves.append(budget_s)
        (reports / "pf_allocation.json").write_text(json.dumps(
            {"generated_utc": f"2026-10-07T12:00:{len(solves):02d}+00:00",
             "heat": {"resolved": 0.2}}), "utf-8")
        return {"rc": 0, "wall_s": 0.1, "tail": ""}

    monkeypatch.setattr(at, "_solve", fake_solve)
    return {"data": data, "solves": solves}


def _request(data: Path, seq: int, fp: str, at_: str) -> None:
    (data / "allocator_resolve_request.json").write_text(json.dumps(
        {"at": at_, "seq": seq, "world_state_fingerprint": fp,
         "requests": [{"event_id": f"e{seq}", "rule": "r"}], "rule": "r"}), "utf-8")


def test_the_watched_request_is_the_one_the_news_stream_writes() -> None:
    watched = {s.path for s in at.sources() if s.kind == "news_resolve_request"}
    assert watched == {nes.RESOLVE_REQUEST}
    assert at.RESOLVE_REQUEST == nes.RESOLVE_REQUEST


def test_a_news_request_fires_the_solve_and_an_unchanged_one_does_not(
        desk: dict[str, Any]) -> None:
    data, solves = desk["data"], desk["solves"]
    st = at.poll(write=False)["state"]                     # first look: nothing to compare yet
    assert solves == []

    _request(data, 1, "fpA", "2026-10-07T11:59:00+00:00")
    res = at.poll(state=st, write=False)
    news = [f for f in res["fired"] if f["kind"] == "news_resolve_request"]
    assert len(solves) == 1 and len(news) == 1
    assert news[0]["source"] == "data/allocator_resolve_request.json"
    assert news[0]["event_at"] == "2026-10-07T11:59:00+00:00"   # the request's own stamp
    assert news[0]["latency_s"] == pytest.approx(61.0) and news[0]["allocation_landed"]

    # The same request rewritten with a fresh `at` is not a new request.
    _request(data, 1, "fpA", "2026-10-07T12:05:00+00:00")
    res = at.poll(state=res["state"], write=False)
    assert res["fired"] == [] and len(solves) == 1

    # The next sequenced request fires again.
    _request(data, 2, "fpB", "2026-10-07T12:06:00+00:00")
    res = at.poll(state=res["state"], write=False)
    assert [f["kind"] for f in res["fired"]] == ["news_resolve_request"] and len(solves) == 2


def test_a_request_is_recorded_in_the_reaction_log_the_gap_reads(desk: dict[str, Any]) -> None:
    data = desk["data"]
    st = at.poll(write=True)["state"]
    _request(data, 7, "fpC", "2026-10-07T11:59:30+00:00")
    at.poll(state=st, write=True)
    rows = [json.loads(x) for x in (data / "allocator_reactions.jsonl").read_text(
        "utf-8").splitlines()]
    assert [r["kind"] for r in rows] == ["news_resolve_request"]
