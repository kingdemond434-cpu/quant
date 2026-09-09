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


class _GraphStub:
    def prior_failures(self, *_a, **_k):
        return {"n_failed": 0, "region": ""}

    def rows(self):
        return []


def _run_main(tmp_path, monkeypatch, rows_by_source: dict[str, list[dict]]) -> dict:
    """Drive `main()` end to end against a temporary tree: no graph, no real universe."""
    import libs.research.hypothesis_graph as hg
    root = tmp_path / "intel"
    for src, rows in rows_by_source.items():
        _write(root, f"{src}/discoveries_1.json", rows)
    monkeypatch.setattr(mcc, "INTEL_ROOTS", (root,))
    monkeypatch.setattr(mcc, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(mcc, "DEEPEN", tmp_path / "deepen.json")
    monkeypatch.setattr(mcc, "known_symbols", lambda: set(UNI))
    monkeypatch.setattr(mcc, "structurally_untestable_families", dict)
    monkeypatch.setattr(hg, "Graph", _GraphStub)
    monkeypatch.setattr(hg, "record_candidates", lambda *a, **k: 0)
    assert mcc.main() == 0
    return {"out": json.loads((tmp_path / "out.json").read_text("utf-8")),
            "deepen": json.loads((tmp_path / "deepen.json").read_text("utf-8"))}


def test_a_prose_row_that_compiles_to_nothing_is_still_deepened(tmp_path, monkeypatch) -> None:
    """REGRESSION for 4aaede35: the per-candidate agreement loop was placed between the
    intake loop's candidate loop and its `if not produced` block, so every non-producing row
    was dropped instead of deepened (and the last row's `produced` decided for all)."""
    res = _run_main(tmp_path, monkeypatch, {"reddit": [
        {"title": "vague EURUSD idea", "text": "EURUSD something happens sometimes"},
        {"kind": "hypothesis", "family": "overnight_gap_decay", "symbols": ["XAUUSD"],
         "title": "structured"}]})
    assert res["out"]["executable_candidates"] == 1
    assert res["out"]["deepening_tasks"] == 1 and len(res["deepen"]["tasks"]) == 1
    assert res["out"]["per_source"]["reddit"] == {"rows": 2, "candidates": 1, "deepening": 1}


def test_two_engines_naming_one_symbol_under_different_families_is_contested(
        tmp_path, monkeypatch) -> None:
    res = _run_main(tmp_path, monkeypatch, {
        "deepseek": [{"kind": "hypothesis", "family": "overnight_gap_decay",
                      "symbols": ["EURUSD"], "title": "a"}],
        "kimi": [{"kind": "hypothesis", "family": "session_range_breakout",
                  "symbols": ["EURUSD"], "title": "b"}],
        "reddit": [{"kind": "hypothesis", "family": "overnight_gap_decay",
                    "symbols": ["XAUUSD"], "title": "c"}]})
    dis = res["out"]["disagreement"]
    assert dis["contested_symbols"] == 1 and set(dis["cells"]) == {"EURUSD"}
    assert set(dis["cells"]["EURUSD"]) == {"overnight_gap_decay", "session_range_breakout"}
    by_sym = {h["symbol"]: h for h in res["out"]["hypotheses"]}
    assert all(h.get("contested") for h in res["out"]["hypotheses"] if h["symbol"] == "EURUSD")
    assert "contested" not in by_sym["XAUUSD"], "one engine, one family: nothing to settle"


def test_a_graph_failure_is_named_in_the_artifact_not_swallowed() -> None:
    src = Path(mcc.__file__).read_text("utf-8")
    block = src.split("THE GRAPH REMEMBERS WHAT WAS BURIED", 1)[1].split("OUT.parent.mkdir", 1)[0]
    assert "except Exception:\n            pass" not in block, "the silent pass is back"
    assert 'graph_note["premortem_why"]' in block and 'graph_note["why"]' in block
    assert '"graph": graph_note' in src


def test_the_candidate_carries_the_genome_id_the_graph_will_use() -> None:
    """A1: stamped at the pen, so the funnel joins by key rather than by matcher."""
    from libs.research.hypothesis_graph import node_id
    rows, _ = mcc.compile_row("deepseek", {"kind": "hypothesis", "family": "overnight_gap_decay",
                                           "symbols": ["EURUSD"], "title": "a"}, UNI)
    assert rows and all(c.get("genome_id") for c in rows)
    for c in rows:
        assert c["genome_id"] == node_id(c["symbol"], c["family"], c["params"])
