"""The deepening worker's memory is bounded by what it needs, not by the graph's age (2026-10-20).

`deepening_worker.py --limit 25` sat at 18 GB in session 0. The limit was never the cause: the
VOI scorer held every row of `hypothesis_graph.jsonl` as a parsed dict (~3.1 KB each) for the
whole pass, and the judge appends up to a million rows per sweep (5,742,434 lines on
2026-10-03). These tests pin the replacement -- the same answers from one streamed read -- and
the rails around it: a memory self-check that checkpoints and exits cleanly, a ledger compaction
that never holds the ledger, and a memory cache that parses once however many threads ask.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import tracemalloc
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(ROOT))

import deepening_worker as dw  # noqa: E402

from libs.research import graveyard_model as gmod  # noqa: E402
from libs.research import hypothesis_graph as hg  # noqa: E402

_GATES = {
    f"gate_{i}": {"passed": i % 3 != 0, "value": i * 0.01, "why": "x" * 40} for i in range(10)
}


def _ledger(path: Path, n_ids: int, *, heavy: bool = False) -> None:
    fams, syms = ("session_range_breakout", "carry", "overnight_gap_decay"), ("EURUSD", "XAUUSD")
    with path.open("w", encoding="utf-8") as fh:
        for i in range(n_ids):
            fam, sym = fams[i % 3], syms[i % 2]
            params = {"lookback": 10 + i % 7}
            region = hg.region_key(sym, fam, params)
            base = {
                "id": f"node-{i}",
                "family": fam,
                "symbol": sym,
                "params": params,
                "region": region,
                "source": "reddit:x",
                "why": "failed dsr",
            }
            # BORN, then a verdict, and for some a later fate that supersedes the first
            fh.write(json.dumps({**base, "fate": "BORN"}) + "\n")
            verdict = "CERTIFIED" if i % 11 == 0 else "FAILED"
            fh.write(
                json.dumps(
                    {
                        **base,
                        "fate": verdict,
                        "gates": _GATES if heavy or verdict == "FAILED" else {},
                    }
                )
                + "\n"
            )
            if i % 5 == 0:
                fh.write(json.dumps({**base, "fate": "BURIED", "gates": _GATES}) + "\n")
            if i % 13 == 0:
                fh.write(json.dumps({**base, "fate": "RETIRED"}) + "\n")
        fh.write(json.dumps({"fate": "FAILED", "region": "no-id-row"}) + "\n")


def _plain(model: gmod.GraveyardModel) -> dict:
    def deep(d):
        return {k: deep(v) if isinstance(v, dict) else v for k, v in d.items()}

    return {
        "n": model.n,
        "class": dict(model.class_counts),
        "surv": dict(model.survive_counts),
        "stage": dict(model.stage_counts),
        "sf": deep(model.survive_feat),
        "ff": deep(model.feat_counts),
    }


def test_the_streamed_index_gives_the_answers_the_whole_graph_gave(tmp_path) -> None:
    p = tmp_path / "hypothesis_graph.jsonl"
    _ledger(p, 400)
    g = hg.Graph(p).snapshot()
    old_counts = {k: len(v) for k, v in g.buried().items()}
    old_model = gmod.GraveyardModel().fit(g.rows())
    model, counts, n = dw.graph_index(p)
    assert n == len(g.rows())
    assert counts == old_counts
    assert _plain(model) == _plain(old_model)
    # the scorer's novelty lookup reads the same count `prior_failures` reported
    for sym, fam, params in (
        ("EURUSD", "session_range_breakout", {"lookback": 10}),
        ("XAUUSD", "carry", {"lookback": 11}),
    ):
        assert (
            counts.get(hg.region_key(sym, fam, params), 0)
            == g.prior_failures(sym, fam, params)["n_failed"]
        )


def test_a_torn_line_costs_one_row_never_the_whole_graph(tmp_path) -> None:
    p = tmp_path / "hypothesis_graph.jsonl"
    _ledger(p, 50)
    _model, clean, n_clean = dw.graph_index(p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "node-x", "fate": "FAI')  # the judge mid-append
    _model, torn, n_torn = dw.graph_index(p)
    assert torn == clean and n_torn == n_clean
    assert hg.Graph(p).snapshot().rows() == [], "the old read discarded everything on it"


def test_the_index_holds_a_small_fraction_of_what_the_snapshot_held(tmp_path) -> None:
    p = tmp_path / "hypothesis_graph.jsonl"
    _ledger(p, 6000, heavy=True)

    def peak(fn) -> int:
        tracemalloc.start()
        try:
            keep = fn()
            _cur, top = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        del keep
        return top

    def old():
        g = hg.Graph(p).snapshot()
        g.buried()
        return g, gmod.GraveyardModel().fit(g.rows())

    before, after = peak(old), peak(lambda: dw.graph_index(p))
    assert after < 0.25 * before, (after, before)


def test_the_memory_guard_reads_live_numbers_and_never_invents_one(monkeypatch) -> None:
    assert dw.memory_guard(rss_mb=9000, avail_mb=10000)[0] is True  # 9 GB > 0.5 x 10 GB
    assert dw.memory_guard(rss_mb=4000, avail_mb=10000)[0] is False
    monkeypatch.setenv("DEEPEN_RSS_SHARE", "1.0")
    assert dw.memory_guard(rss_mb=9000, avail_mb=10000)[0] is False
    monkeypatch.setenv("DEEPEN_RSS_SHARE", "junk")
    assert dw.memory_guard(rss_mb=9000, avail_mb=10000)[0] is True
    over, why = dw.memory_guard()  # this machine, now
    assert isinstance(over, bool) and "available" in why


def _isolate(tmp_path, monkeypatch, tasks: list[dict]) -> None:
    q = tmp_path / "queue.json"
    q.write_text(json.dumps({"tasks": tasks}), "utf-8")
    for name, f in (
        ("DEEPEN", q),
        ("WORKED", tmp_path / "worked.jsonl"),
        ("OUT", tmp_path / "deepened.json"),
        ("LOG", tmp_path / "log.txt"),
        ("LOCK", tmp_path / ".lock"),
        ("BUDGET", tmp_path / "budget.json"),
        ("BACKLOG", tmp_path / "backlog.json"),
        ("THROUGHPUT", tmp_path / "throughput.json"),
        ("MEMORY_GUARD_REPORT", tmp_path / "DEEPENING_MEMORY_GUARD.json"),
    ):
        monkeypatch.setattr(dw, name, f)
    monkeypatch.setattr(dw, "known_symbols", lambda: set())
    monkeypatch.setattr(dw, "_scorer", lambda: lambda t: 1.0)
    monkeypatch.setattr(dw, "_seat_budget", lambda: (100, "test budget"))
    monkeypatch.setattr(dw, "compile_row", lambda *a, **k: ([], "EMPTY_CAPTURE"))
    monkeypatch.setattr(dw, "work_task", lambda task, universe: ([], "REJECTED: test"))


def _tasks(n: int) -> list[dict]:
    rule = [
        {"source": "s", "url": f"u{i}", "title": f"rule {i}", "disposition": "EMPTY_CAPTURE"}
        for i in range(n)
    ]
    seat = [
        {
            "source": "s",
            "url": f"v{i}",
            "title": f"seat {i}",
            "disposition": "NEEDS_SYMBOL_EXTRACTION",
        }
        for i in range(n)
    ]
    return rule + seat


def test_over_memory_the_pass_checkpoints_and_exits_cleanly_and_the_next_resumes(
    tmp_path, monkeypatch
) -> None:
    _isolate(tmp_path, monkeypatch, _tasks(6))
    calls = {"n": 0}

    def guard():
        calls["n"] += 1
        return calls["n"] > 3, "rss 9000MB vs 0.5 x 10000MB available = 5000MB"

    monkeypatch.setattr(dw, "memory_guard", guard)
    assert dw.main([]) == 0
    first = [json.loads(ln) for ln in dw.WORKED.read_text("utf-8").splitlines() if ln]
    # the guard is first asked AFTER task 1 (a pass always does one), so: 1 + 3 decided
    assert len(first) == 4, "four decided, then it stopped starting work"
    out = json.loads(dw.OUT.read_text("utf-8"))
    assert out["memory_guard"]["why"].startswith("rss 9000MB")
    # THE NEXT PASS RESUMES: nothing decided is redone, nothing undecided is lost
    monkeypatch.setattr(dw, "memory_guard", lambda: (False, "ok"))
    assert dw.main([]) == 0
    rows = [json.loads(ln) for ln in dw.WORKED.read_text("utf-8").splitlines() if ln]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) == 12, "every task decided exactly once across the two"


def test_a_ledger_of_decisions_is_never_rewritten_and_never_held(tmp_path) -> None:
    p = tmp_path / "worked.jsonl"
    p.write_text(
        "".join(
            json.dumps(
                {"id": f"t{i}", "disposition": "REJECTED: x", "at": "2026-10-20T00:00:00+00:00"}
            )
            + "\n"
            for i in range(200)
        ),
        "utf-8",
    )
    st = os.stat(p)
    got = dw.compact_ledger(p, over_bytes=10)
    assert got["compacted"] is False and "every line is a decision" in got["why"]
    assert os.stat(p).st_mtime_ns == st.st_mtime_ns
    with p.open("a", encoding="utf-8") as fh:
        for i in range(5):
            fh.write(
                json.dumps(
                    {
                        "id": f"o{i}",
                        "at": "2026-10-20T01:00:00+00:00",
                        "disposition": "BLOCKED_SEAT_UNAVAILABLE: none",
                    }
                )
                + "\n"
            )
    got = dw.compact_ledger(p, over_bytes=10)
    assert got["compacted"] is True and got["outage_rows_dropped"] == 4
    rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln]
    assert len(rows) == 201 and sum(r["id"].startswith("t") for r in rows) == 200


def test_the_memory_cache_is_parsed_once_however_many_threads_ask(tmp_path, monkeypatch):
    from libs.research import memory

    mdir = tmp_path / "memory"
    mdir.mkdir()
    (mdir / "failure.jsonl").write_text(
        "".join(
            json.dumps({"id": f"m{i}", "kind": "failure", "key": "k", "text": f"EURUSD carry {i}"})
            + "\n"
            for i in range(2000)
        ),
        "utf-8",
    )
    built: list[int] = []
    real = memory._Ledger

    class Counting(real):  # type: ignore[misc,valid-type]
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            if self.stamp is not None:
                built.append(1)

    monkeypatch.setattr(memory, "_Ledger", Counting)
    monkeypatch.setattr(memory, "_CACHE", {})
    gate = threading.Barrier(8)
    seen: list[int] = []

    def ask() -> None:
        gate.wait()
        seen.append(len(memory.recall("failure", "EURUSD carry", k=3, memory_dir=mdir)))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen == [3] * 8
    assert len(built) == 1, f"parsed {len(built)} times for 8 concurrent askers"


def test_a_tripped_guard_still_works_one_task_and_publishes_what_it_deferred(
    tmp_path, monkeypatch
) -> None:
    """Audit of 2832cebd1: checked before the first task, the guard could stop every pass at
    ZERO tasks and exit 0 each hour -- a silent mining cut. A pass now always does one, and
    publishes the deferred count, the run of consecutive tripped passes and a missed-growth line."""
    _isolate(tmp_path, monkeypatch, _tasks(6))
    monkeypatch.setattr(dw, "memory_guard", lambda: (True, "rss 9000MB vs 0.5 x 1000MB"))
    assert dw.main([]) == 0
    rows = [ln for ln in dw.WORKED.read_text("utf-8").splitlines() if ln]
    assert len(rows) == 1, "a tripped guard still decides one task"
    rep = json.loads(dw.MEMORY_GUARD_REPORT.read_text("utf-8"))
    assert rep["tripped"] is True and rep["worked_this_pass"] == 1
    assert rep["deferred"] == 11 and rep["consecutive_tripped"] == 1
    line = rep["missed_growth"][-1]
    assert line["rail"] == "deepening_memory_guard" and line["deferred"] == 11
    assert line["verdict"] == "UNMEASURED" and line["value"] is None
    assert dw.main([]) == 0  # the next pass: one more task
    rep = json.loads(dw.MEMORY_GUARD_REPORT.read_text("utf-8"))
    assert rep["consecutive_tripped"] == 2 and rep["worked_this_pass"] == 1
    assert len([ln for ln in dw.WORKED.read_text("utf-8").splitlines() if ln]) == 2
    monkeypatch.setattr(dw, "memory_guard", lambda: (False, "ok"))
    assert dw.main([]) == 0  # an untripped pass resets the run
    rep = json.loads(dw.MEMORY_GUARD_REPORT.read_text("utf-8"))
    assert rep["tripped"] is False and rep["consecutive_tripped"] == 0 and rep["deferred"] == 0
    assert rep["tripped_passes_total"] == 2 and len(rep["missed_growth"]) == 2


def test_the_guard_lines_reach_missed_growth(tmp_path, monkeypatch) -> None:
    if str(DESK) not in sys.path:
        sys.path.insert(0, str(DESK))
    import research.missed_growth as mg

    path = tmp_path / "DEEPENING_MEMORY_GUARD.json"
    assert mg.organ_published_lines(path)["verdict"] == "UNMEASURED"
    dw.publish_memory_guard({}, worked=5, pending=5, path=path)
    assert mg.organ_published_lines(path)["verdict"] == "NOT_BINDING"
    dw.publish_memory_guard({"why": "rss"}, worked=1, pending=9, path=path)
    got = mg.organ_published_lines(path)
    assert got["verdict"] == "UNMEASURED" and got["lines"][0]["deferred"] == 8
    assert got["consecutive"] == 1


def test_outage_rows_never_satisfy_the_one_task_guarantee(tmp_path, monkeypatch) -> None:
    """Audit of 7cf2ece90: an outage row (a seat unavailable) is not work. A pass whose only
    commits are outages has decided nothing, so the guard is never allowed to stop it there."""
    seat = [t for t in _tasks(3) if t["disposition"] == "NEEDS_SYMBOL_EXTRACTION"]
    _isolate(tmp_path, monkeypatch, seat)
    monkeypatch.setenv("DEEPEN_SEAT_WORKERS", "1")
    monkeypatch.setattr(dw, "work_task", lambda task, universe: ([], "REJECTED: seat error: down"))
    asked = {"n": 0}

    def guard():
        asked["n"] += 1
        return True, "rss 9000MB vs 0.5 x 1000MB"

    monkeypatch.setattr(dw, "memory_guard", guard)
    assert dw.main([]) == 0
    rows = [json.loads(ln) for ln in dw.WORKED.read_text("utf-8").splitlines() if ln]
    assert len(rows) == 3 and all(dw.is_outage(r["disposition"]) for r in rows)
    assert asked["n"] == 0, "no real decision yet, so the guard was never consulted"
    rep = json.loads(dw.MEMORY_GUARD_REPORT.read_text("utf-8"))
    assert rep["worked_this_pass"] == 0 and rep["tripped"] is False
