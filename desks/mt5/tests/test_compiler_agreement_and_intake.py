"""Four things the compiler used to know and throw away: which seats donated nothing, how many
engines agree on a cell, why the graph annotation failed, and how many files the intake bound
left unread.

MEASURED 2026-09-08 on the box: 632 of 632 compiled candidates carried no premortem and no
prior-failure count while the code that stamps them ran every hour inside `except: pass`; the
MAX_ROWS_PER_PASS shortfall was a printed line; two engines naming the same cell collided on one
identity and the collision was discarded; a seat that donated nothing looked like a quiet seat.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import miner_candidate_compiler as mcc  # noqa: E402

UNI = {"EURUSD", "XAUUSD"}


def _write(root: Path, rel: str, rows: list[dict]) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"discoveries": rows}), "utf-8")
    return p


@pytest.fixture
def roots(tmp_path, monkeypatch):
    a = tmp_path / "intel"
    a.mkdir()
    monkeypatch.setattr(mcc, "INTEL_ROOTS", (a,))
    return a


def test_the_intake_bound_records_how_many_files_it_left_unread(roots, monkeypatch) -> None:
    for i in range(4):
        _write(roots, f"src{i}/discoveries_{i}.json", [{"title": f"r{i}", "symbol": "EURUSD"}])
    monkeypatch.setattr(mcc, "MAX_ROWS_PER_PASS", 1)
    rows = mcc.recent_rows(mcc.datetime.now(tz=mcc.UTC))
    assert len(rows) == 1
    assert mcc._LAST_INTAKE["bound_hit"] is True
    assert mcc._LAST_INTAKE["deferred_files"] == 3, "three files were never opened this pass"
    monkeypatch.setattr(mcc, "MAX_ROWS_PER_PASS", 1_000_000)
    mcc.recent_rows(mcc.datetime.now(tz=mcc.UTC))
    assert mcc._LAST_INTAKE["bound_hit"] is False and mcc._LAST_INTAKE["deferred_files"] == 0


def test_seats_that_donated_nothing_are_named() -> None:
    seats = mcc.seat_summary({"deepseek": {"rows": 3, "candidates": 1, "deepening": 2}})
    dark = [s for s, st in seats.items() if not st["rows"]]
    assert dark == ["kimi_k3_deep_forest"]
    src = Path(mcc.__file__).read_text("utf-8")
    assert '"seats_dark": seats_dark' in src and "SEATS DARK" in src


def test_two_engines_naming_the_same_cell_are_counted_as_agreement() -> None:
    """The dedup collision that used to be discarded is the agreement signal."""
    a = {"kind": "hypothesis", "symbols": ["EURUSD"], "family": "overnight_gap_decay",
         "title": "a", "source": "deepseek"}
    b = {"symbols": ["EURUSD"], "text": "EURUSD gap fill at the open", "source": "reddit"}
    ca, _ = mcc.compile_row("deepseek", a, UNI)
    cb, _ = mcc.compile_row("reddit", b, UNI)
    ident = lambda c: json.dumps({k: c[k] for k in ("symbol", "family", "params")},  # noqa: E731
                                 sort_keys=True, default=str)
    same = {ident(c) for c in ca} & {ident(c) for c in cb}
    assert same, "the two rows must compile to one identical cell for this test to bite"
    src = Path(mcc.__file__).read_text("utf-8")
    assert "n_independent_sources" in src and '"agreement":' in src


def test_a_graph_failure_is_named_in_the_artifact_not_swallowed() -> None:
    src = Path(mcc.__file__).read_text("utf-8")
    block = src.split("THE GRAPH REMEMBERS WHAT WAS BURIED", 1)[1].split("OUT.parent.mkdir", 1)[0]
    assert "except Exception:\n            pass" not in block, "the silent pass is back"
    assert 'graph_note["premortem_why"]' in block and 'graph_note["why"]' in block
    assert '"graph": graph_note' in src
