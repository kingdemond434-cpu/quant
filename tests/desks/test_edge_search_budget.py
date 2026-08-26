"""The family-free searcher must finish 40 symbols, not fail at 295 (gap-fixer 2026-08-26).

`PER_RUN = 40` was computed, written into the rotation cursor, and never applied as a slice.
The code's own comment refused to truncate on the grounds that "the desk box ... currently fits
the complete Fusion registry in one hourly run". It does not:

    covering the complete registry: 295 symbol(s) this run
    File "...\\research\\edge_search.py", line 427, in evaluate
    MemoryError

The process died partway, so edge_search_results.json was never written, the pipeline logged
`family-free frontier pull FAILED`, and the merge received nothing from the one organ whose job
is to break the book's concentration. Measured at the time: the artifact was 3.8h stale across
two completed pipeline runs, and 20 of 21 certificates were session_range_breakout (0.952).

Slicing is not timidity here and the arithmetic is the argument: 295 attempted completes ZERO;
40 that complete, hourly, is ~960 symbol-searches a day against the current zero. Coverage stays
a CYCLE (RESEARCH 6c-bis) -- the cursor advances every run and every symbol comes back.
"""
from __future__ import annotations

import json

from desks.mt5.research import edge_search


def _universe(tmp_path, names):
    """main() enumerates the registry from parquet FILENAMES, so names are all a test needs."""
    d = tmp_path / "universe"
    d.mkdir(exist_ok=True)
    for n in names:
        (d / f"{n}_H1.parquet").write_bytes(b"")
    return d


def test_per_run_budget_is_a_real_slice(tmp_path, monkeypatch, capsys):
    """The defect verbatim: a registry far larger than the budget must be sliced, not attempted."""
    searched: list[str] = []
    monkeypatch.setattr(edge_search, "PER_RUN", 5)
    monkeypatch.setattr(edge_search, "BASE", tmp_path)
    monkeypatch.setattr(edge_search, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(edge_search, "UNIVERSE",
                        _universe(tmp_path, [f"SYM{i:03d}" for i in range(295)]))
    monkeypatch.setattr(edge_search, "search_symbol",
                        lambda s: (searched.append(s), {"symbol": s, "trials": 1,
                                                        "selected": []})[1])
    edge_search.main()
    assert len(searched) <= 20, f"budget not applied: {len(searched)} symbols attempted"
    assert "budgeted slice" in capsys.readouterr().out


def test_the_cursor_still_advances_so_coverage_is_a_cycle(tmp_path, monkeypatch):
    """A budget that pinned the same 40 symbols forever would be the WS-005 error in a new
    costume -- absence of a fresh look read as absence of an edge."""
    monkeypatch.setattr(edge_search, "PER_RUN", 5)
    monkeypatch.setattr(edge_search, "BASE", tmp_path)
    monkeypatch.setattr(edge_search, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(edge_search, "UNIVERSE",
                        _universe(tmp_path, [f"SYM{i:03d}" for i in range(60)]))
    seen_runs = []

    def _capture(s):
        seen_runs.append(s)
        return {"symbol": s, "trials": 1, "selected": []}

    monkeypatch.setattr(edge_search, "search_symbol", _capture)
    edge_search.main()
    first = list(seen_runs)
    seen_runs.clear()
    edge_search.main()
    assert first != seen_runs, "the cursor did not rotate -- coverage is a sweep, not a cycle"


def test_one_symbols_memoryerror_does_not_void_the_run(tmp_path, monkeypatch):
    """THE FAILURE MODE THAT COST WHOLE HOURS. One symbol exhausting memory killed the process
    and therefore every other symbol's work in the same run."""
    monkeypatch.setattr(edge_search, "PER_RUN", 10)
    monkeypatch.setattr(edge_search, "BASE", tmp_path)
    out = tmp_path / "out.json"
    monkeypatch.setattr(edge_search, "OUT", out)
    monkeypatch.setattr(edge_search, "UNIVERSE", _universe(tmp_path, ["A", "BOOM", "C"]))

    def _search(s):
        if s == "BOOM":
            raise MemoryError("evaluate")
        return {"symbol": s, "trials": 1, "selected": []}

    monkeypatch.setattr(edge_search, "search_symbol", _search)
    edge_search.main()
    doc = json.loads(out.read_text("utf-8"))
    assert doc["symbols"] == 2, doc["symbols"]
    assert [r["symbol"] for r in doc["unsearched"]] == ["BOOM"]


def test_a_skipped_symbol_is_not_reported_as_searched(tmp_path, monkeypatch):
    """RECORDED, NEVER SWALLOWED. A symbol that blew up was NOT searched-and-found-nothing, and
    conflating the two is absence read as a verdict. `symbols` counts completions; a reader can
    see the offered count and the skips separately."""
    monkeypatch.setattr(edge_search, "PER_RUN", 10)
    monkeypatch.setattr(edge_search, "BASE", tmp_path)
    out = tmp_path / "out.json"
    monkeypatch.setattr(edge_search, "OUT", out)
    monkeypatch.setattr(edge_search, "UNIVERSE", _universe(tmp_path, ["A", "BOOM"]))
    monkeypatch.setattr(edge_search, "search_symbol",
                        lambda s: (_ for _ in ()).throw(MemoryError()) if s == "BOOM"
                        else {"symbol": s, "trials": 1, "selected": []})
    edge_search.main()
    doc = json.loads(out.read_text("utf-8"))
    assert doc["symbols"] == 1 and doc["symbols_offered"] == 2
    assert doc["unsearched"], "a skipped symbol vanished from the record"
