"""The per-pass seat census: a heartbeat that tells "ran, found nothing new" from "dead".

Measured on the box 2026-11-11: fifteen hourly legs closed LEG_DONE ok while their seats read days
stale, because each donates only NEW rows. `proposer_common.pass_census` is the one small file a
real pass rewrites in its seat. It must never carry a row the compiler would read as evidence.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import index_discovery as idx  # noqa: E402
from research import miner_candidate_compiler as mc  # noqa: E402
from research import proposer_common as pc  # noqa: E402


def test_the_census_is_written_into_the_seat_and_carries_no_row(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    path = pc.pass_census("some_seat", tried=40, new=0, duplicate=40, donated=0, leg="some_leg",
                          by_reason={"duplicate_cell": 40},
                          rows=[{"symbol": "EURUSD", "family": "lead_lag"}])
    assert path == tmp_path / "intel" / "some_seat" / pc.CENSUS_NAME
    doc = json.loads(path.read_text("utf-8"))
    assert (doc["tried"], doc["new"], doc["duplicate"], doc["donated"]) == (40, 0, 40, 0)
    assert doc["kind"] == "pass_census" and doc["leg"] == "some_leg"
    assert doc["by_reason"] == {"duplicate_cell": 40}
    # a list of dicts would be read as rows by the compiler: it is dropped, never written
    assert "rows" not in doc
    assert list(mc._iter_file_rows(path)) == []
    # rewritten in place, never accumulated
    pc.pass_census("some_seat", tried=1, new=1)
    assert [p.name for p in path.parent.iterdir()] == [pc.CENSUS_NAME]
    assert json.loads(path.read_text("utf-8"))["new"] == 1


def test_an_explicit_seat_dir_wins_and_a_failure_never_raises(tmp_path: Path) -> None:
    out = pc.pass_census("x", tried=1, new=0, seat_dir=tmp_path / "own")
    assert out == tmp_path / "own" / pc.CENSUS_NAME and out.exists()
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", "utf-8")
    assert pc.pass_census("x", tried=1, new=0, seat_dir=blocker / "seat") is None


def test_index_discovery_writes_its_seat_inside_its_own_deadline(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The organ battery kills a member at its 150 s slice, and this organ wrote its seat only
    after its last route. With the deadline spent, no request is started, no route runs, and the
    report and the seat are still written."""
    monkeypatch.setattr(idx, "OUT", tmp_path / "INDEX_DISCOVERY.json")
    monkeypatch.setattr(idx, "FOUND", tmp_path / "intel" / "index_discovery")
    called: list[str] = []
    monkeypatch.setattr(idx, "ROUTES", {"a": lambda n: called.append("a") or {"route": "a"},
                                        "b": lambda n: called.append("b") or {"route": "b"}})
    monkeypatch.setattr(idx, "_DEADLINE", None)      # restored after the test
    clock = iter([0.0])
    # the module's own clock only: the deadline is set at t=0 and every later read is far past it
    monkeypatch.setattr(idx, "time", SimpleNamespace(monotonic=lambda: next(clock, 1e9),
                                                     time=time.time))
    assert idx.main(["--budget-s", "5"]) == 0
    assert called == []
    doc = json.loads((tmp_path / "INDEX_DISCOVERY.json").read_text("utf-8"))
    assert all("budget" in str(v.get("route")) for v in doc["errors"].values())
    assert list((tmp_path / "intel" / "index_discovery").glob("addresses_*.json"))


def test_a_request_past_the_deadline_is_not_started(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(idx, "_DEADLINE", idx.time.monotonic() - 1.0)

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("a request was started past the deadline")

    monkeypatch.setattr(idx.urllib.request, "urlopen", boom)
    body, why = idx._get("https://example.invalid/")
    assert body is None and why.startswith("budget")
