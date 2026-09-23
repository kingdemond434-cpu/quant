"""The deepening queue had no reader, and a reader that invents rules is worse than none.

    python -m pytest desks/mt5/tests/test_deepening_worker.py -q

705 tasks sat at status None because the only module naming the queue file was the one that
WRITES it. Adding a reader is easy; adding one that cannot fabricate is the job. An LLM shown
"Build adaptive algorithmic trading bots ... for MetaTrader 5 scalping" will happily return a
complete EURUSD scalping rule with parameters, and every field of it would be invention wearing
the miner's provenance.

WHAT MUST NOT REGRESS, in order of what it would cost:

  1. an extraction whose `evidence` is not verbatim in the source text is REJECTED
  2. a symbol outside the desk universe cannot be admitted by naming it
  3. nothing reaches the candidate store except through `compile_row`
  4. a task is billed once -- a decision, including a rejection, is final
  5. one bad row does not end the batch
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESK / "research"))

import deepening_worker as dw  # noqa: E402

_TASK = {
    "source": "world_crawler",
    "disposition": "NEEDS_SYMBOL_EXTRACTION",
    "title": "EURUSD London open range breakout, 20-bar lookback",
    "url": "https://example.invalid/post",
    "symbols": [],
    "mechanism_tags": ["breakout"],
}


def _chat(payload: dict | str):
    """A seat that returns exactly what the test dictates."""
    body = payload if isinstance(payload, str) else json.dumps(payload)

    def chat(prompt, **kw):        # noqa: ARG001
        return body, ""
    return chat


# ------------------------------------------------- 1. fabrication is caught, not trusted

def test_an_evidence_span_absent_from_the_source_is_rejected() -> None:
    """The one guard that matters: a confident answer the text does not support."""
    found, why = dw.extract(_TASK, chat=_chat({
        "symbols": ["EURUSD"], "family": "session_range_breakout",
        "params": {"lookback": 20},
        "evidence": "the author backtested this over 11 years of tick data",
    }))
    assert found == {}
    assert "fabricated quote" in why


def test_a_verbatim_span_is_accepted() -> None:
    found, why = dw.extract(_TASK, chat=_chat({
        "symbols": ["EURUSD"], "family": "session_range_breakout",
        "params": {"lookback": 20},
        "evidence": "EURUSD London open range breakout",
    }))
    assert why == ""
    assert found["symbols"] == ["EURUSD"]


def test_requoting_with_different_whitespace_still_counts() -> None:
    """Models re-wrap lines while quoting faithfully; that is not a fabrication."""
    found, why = dw.extract(_TASK, chat=_chat({
        "symbols": ["EURUSD"], "family": None, "params": None,
        "evidence": "EURUSD   London\n  open range breakout",
    }))
    assert why == "", why
    assert found["symbols"] == ["EURUSD"]


# ------------------------------------------------- 2. the model cannot widen the desk's sets

def test_a_symbol_outside_the_universe_cannot_be_admitted_by_naming_it() -> None:
    found, why = dw.validate(
        {"symbols": ["DOGEUSD"], "family": None, "params": None, "evidence": "DOGEUSD"},
        "DOGEUSD is the instrument", {"EURUSD", "XAUUSD"})
    assert found == {}
    assert "outside the desk universe" in why


def test_nested_params_are_refused() -> None:
    found, why = dw.validate(
        {"symbols": ["EURUSD"], "family": "f", "params": {"a": {"b": 1}}, "evidence": "x"},
        "x", {"EURUSD"})
    assert found == {} and "flat scalars" in why


def test_an_empty_extraction_is_a_result_not_an_error() -> None:
    found, why = dw.validate(
        {"symbols": [], "family": None, "params": None, "why_not": "no instrument named"},
        "text", {"EURUSD"})
    assert found == {}
    assert "no instrument named" in why


# ------------------------------------------------- 3. only compile_row may mint a candidate

def test_a_recovered_row_goes_back_through_the_compiler(monkeypatch) -> None:
    """The reader must not be a second admission door into the candidate store."""
    seen: dict = {}

    def fake_compile(source, row, universe):     # noqa: ARG001
        seen["row"] = row
        return [{"symbol": "EURUSD", "family": "session_range_breakout"}], "EXACT_RECIPE"

    monkeypatch.setattr(dw, "compile_row", fake_compile)
    out, disposition = dw.work_task(_TASK, {"EURUSD"}, chat=_chat({
        "symbols": ["EURUSD"], "family": "session_range_breakout",
        "params": {"lookback": 20}, "evidence": "20-bar lookback",
    }))
    assert disposition == "RECOVERED_EXACT_RECIPE"
    assert out and out[0]["deepened"] is True
    assert seen["row"]["symbols"] == ["EURUSD"], "the recovered symbol must reach the compiler"
    assert seen["row"]["url"] == _TASK["url"], "the original row must be carried, not replaced"


def test_the_compiler_may_still_refuse_a_recovered_row(monkeypatch) -> None:
    """Recovery is not admission. The compiler's verdict stands."""
    monkeypatch.setattr(dw, "compile_row",
                        lambda *a, **k: ([], "NEEDS_EXACT_RULE_EXTRACTION"))
    out, disposition = dw.work_task(_TASK, {"EURUSD"}, chat=_chat({
        "symbols": ["EURUSD"], "family": None, "params": None,
        "evidence": "EURUSD London open range breakout",
    }))
    assert out == []
    assert disposition == "STILL_NEEDS_EXACT_RULE_EXTRACTION"


def test_a_rejected_extraction_never_reaches_the_compiler(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(dw, "compile_row", lambda *a, **k: called.append(1) or ([], "X"))
    out, disposition = dw.work_task(_TASK, {"EURUSD"}, chat=_chat({
        "symbols": ["EURUSD"], "family": None, "params": None,
        "evidence": "a sentence that is nowhere in the row",
    }))
    assert out == [] and disposition.startswith("REJECTED")
    assert not called, "a rejected extraction must not be compiled"


# ------------------------------------------------- 4. a decision is paid for once

def test_a_task_id_is_stable_across_queue_rebuilds() -> None:
    """The queue is rewritten hourly; identity must come from the row, not its position."""
    a = dict(_TASK)
    b = dict(_TASK)
    b["disposition"] = "NEEDS_EXACT_RULE_EXTRACTION"      # compiler re-dispositioned it
    assert dw.task_id(a) == dw.task_id(b)
    c = dict(_TASK, url="https://example.invalid/other")
    assert dw.task_id(c) != dw.task_id(a)


def test_worked_ids_survives_a_corrupt_line(tmp_path, monkeypatch) -> None:
    led = tmp_path / "worked.jsonl"
    led.write_text('{"id":"aaa"}\nnot json\n{"no_id":1}\n{"id":"bbb"}\n', encoding="utf-8")
    monkeypatch.setattr(dw, "WORKED", led)
    assert dw.worked_ids() == {"aaa", "bbb"}


# ------------------------------------------------- 5. robustness of the batch

def test_a_reply_that_is_not_json_is_a_rejection_not_a_crash() -> None:
    found, why = dw.extract(_TASK, chat=_chat("I think you should trade EURUSD!"))
    assert found == {} and "not a JSON object" in why


def test_a_fenced_json_reply_is_still_read() -> None:
    body = '```json\n{"symbols":["EURUSD"],"family":null,"params":null,' \
           '"evidence":"20-bar lookback"}\n```'
    found, why = dw.extract(_TASK, chat=_chat(body))
    assert why == "", why
    assert found["symbols"] == ["EURUSD"]


def test_a_seat_error_is_reported_never_raised() -> None:
    def chat(prompt, **kw):        # noqa: ARG001
        return "", "budget exhausted"
    found, why = dw.extract(_TASK, chat=chat)
    assert found == {} and "budget exhausted" in why


# ------------------------------------------------- the score has a denominator now

class TestCostDenominator:
    """`voi_order` had no cost term: a task worth 2 that takes 40 seconds of seat time sat ahead
    of one worth 1.5 that takes 3. The score is now divided by the class's MEASURED mean wall
    seconds, read through `compute_ledger.cost_by_run` from the worked ledger's own rows; an
    uncosted class divides by 1.0 so the order is exactly what it was."""

    def test_a_cheaper_class_of_equal_worth_is_worked_first(self) -> None:
        a = dict(_TASK, kind="fund_claim", title="a")
        b = dict(_TASK, kind="coverage_gap", title="b")
        one = lambda t: 1.0                                                   # noqa: E731
        costs = {"deepen:fund_claim": 40.0, "deepen:coverage_gap": 4.0}
        assert [t["title"] for t in dw.voi_order([a, b], costs=costs, scorer=one)] == ["b", "a"]
        flipped = {"deepen:fund_claim": 4.0, "deepen:coverage_gap": 40.0}
        assert [t["title"] for t in dw.voi_order([a, b], costs=flipped, scorer=one)] == ["a", "b"]

    def test_an_uncosted_queue_orders_exactly_as_before(self) -> None:
        tasks = [dict(_TASK, title=f"t{i}", kind="k") for i in range(6)]
        ref = sorted(tasks, key=lambda t: (-1.0, dw.task_id(t)))
        assert dw.voi_order(tasks, costs={}, scorer=lambda t: 1.0) == ref
        assert dw.voi_order(tasks, costs=None, scorer=lambda t: 1.0) == ref
        assert dw.voi_order(tasks, costs={"deepen:other": 99.0}, scorer=lambda t: 1.0) == ref

    def test_a_sub_second_class_is_floored_not_promoted_by_clock_noise(self) -> None:
        a = dict(_TASK, kind="x", title="a")
        b = dict(_TASK, kind="y", title="b")
        costs = {"deepen:x": 0.01, "deepen:y": dw.MIN_TASK_COST_S}
        got = dw.voi_order([a, b], costs=costs, scorer=lambda t: 1.0)
        assert got == sorted([a, b], key=dw.task_id), "0.01s and 1.0s must tie at the floor"

    def test_task_costs_reads_the_worked_ledger_through_cost_by_run(self, tmp_path,
                                                                    monkeypatch) -> None:
        from datetime import UTC, datetime
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        led = tmp_path / "worked.jsonl"
        led.write_text("\n".join([
            json.dumps({"id": "old", "at": now, "disposition": "REJECTED"}),   # pre-stamp row
            json.dumps({"id": "a", "at": now, "run": "deepen:fund_claim", "wall_s": 10.0}),
            json.dumps({"id": "b", "at": now, "run": "deepen:fund_claim", "wall_s": 30.0}),
            json.dumps({"id": "c", "at": now, "run": "deepen:anomaly", "wall_s": 0.0}),
        ]) + "\n", encoding="utf-8")
        monkeypatch.setattr(dw, "WORKED", led)
        costs, basis = dw.task_costs()
        assert costs == {"deepen:fund_claim": 20.0}, "a class at 0.0s is not a measurement"
        assert basis.startswith("measured") and "cost_by_run" in basis

    def test_no_costed_rows_is_uncosted_and_says_the_order_is_unchanged(self, tmp_path,
                                                                        monkeypatch) -> None:
        monkeypatch.setattr(dw, "WORKED", tmp_path / "none.jsonl")
        costs, basis = dw.task_costs()
        assert costs == {} and basis.startswith("uncosted") and "unchanged" in basis

    def test_controller_variant_is_read_when_present_else_none(self, tmp_path,
                                                                monkeypatch) -> None:
        monkeypatch.setattr(dw, "BUDGET", tmp_path / "research_budget.json")
        assert dw.controller_variant() is None
        dw.BUDGET.write_text(json.dumps({"shares": {}, "controller_variant": "B"}), "utf-8")
        assert dw.controller_variant() == "B"
        dw.BUDGET.write_text(json.dumps({"shares": {}}), "utf-8")
        assert dw.controller_variant() is None, "absence is None, not a default arm"

    def _isolate(self, tmp_path, monkeypatch, tasks: list[dict], variant: str | None) -> None:
        q = tmp_path / "queue.json"
        q.write_text(json.dumps({"tasks": tasks}), "utf-8")
        monkeypatch.setattr(dw, "DEEPEN", q)
        monkeypatch.setattr(dw, "WORKED", tmp_path / "worked.jsonl")
        monkeypatch.setattr(dw, "OUT", tmp_path / "deepened.json")
        monkeypatch.setattr(dw, "LOG", tmp_path / "log.txt")
        monkeypatch.setattr(dw, "LOCK", tmp_path / ".lock")
        monkeypatch.setattr(dw, "BUDGET", tmp_path / "research_budget.json")
        if variant is not None:
            dw.BUDGET.write_text(json.dumps({"controller_variant": variant}), "utf-8")
        monkeypatch.setattr(dw, "known_symbols", lambda: set())
        monkeypatch.setattr(dw, "work_task", lambda task, universe: ([], "REJECTED: test"))

    def test_the_worked_row_carries_class_seconds_basis_and_variant(self, tmp_path,
                                                                    monkeypatch) -> None:
        self._isolate(tmp_path, monkeypatch,
                      [dict(_TASK, kind="fund_claim", title="first")], variant="B")
        assert dw.main([]) == 0
        rows = [json.loads(ln) for ln in dw.WORKED.read_text("utf-8").splitlines() if ln]
        assert len(rows) == 1
        row = rows[0]
        assert row["run"] == "deepen:fund_claim" and row["kind"] == "fund_claim"
        assert isinstance(row["wall_s"], float) and row["wall_s"] >= 0.0
        assert row["cost_basis"] == "uncosted:1.0", "nothing measured yet: the order was unchanged"
        assert row["controller_variant"] == "B"
        assert row["disposition"] == "REJECTED: test", "the existing fields are untouched"

    def test_the_next_run_prices_the_class_from_the_rows_the_last_one_wrote(self, tmp_path,
                                                                            monkeypatch) -> None:
        from datetime import UTC, datetime
        self._isolate(tmp_path, monkeypatch,
                      [dict(_TASK, kind="fund_claim", title="second")], variant=None)
        dw.WORKED.write_text(json.dumps({
            "id": "earlier", "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "run": "deepen:fund_claim", "wall_s": 12.0}) + "\n", "utf-8")
        assert dw.main([]) == 0
        rows = [json.loads(ln) for ln in dw.WORKED.read_text("utf-8").splitlines() if ln]
        assert rows[-1]["cost_basis"] == "measured:deepen:fund_claim:12.00s"
        assert rows[-1]["controller_variant"] is None, "no variant in the budget file: None"

def test_a_seat_outage_blocks_instead_of_rejecting_the_source() -> None:
    """Credential absence is a retry dependency, never a verdict on the lead."""
    def chat(prompt, **kw):
        return "", "no seat: export OPENROUTER_API_KEY"

    out, disposition = dw.work_task(_TASK, {"EURUSD"}, chat=chat)
    assert out == []
    assert disposition.startswith("BLOCKED_SEAT_UNAVAILABLE: seat error:")


def test_seat_blocked_tasks_reopen_only_when_a_seat_is_available(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "worked.jsonl"
    ledger.write_text(
        '{"id":"old","disposition":"REJECTED: seat error: no seat"}\n'
        '{"id":"new","disposition":"BLOCKED_SEAT_UNAVAILABLE: seat error: no seat"}\n'
        '{"id":"terminal","disposition":"REJECTED: fabricated quote"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(dw, "WORKED", ledger)
    assert dw.worked_ids() == {"old", "new", "terminal"}
    assert dw.worked_ids(retry_seat_blocks=True) == {"terminal"}



# ------------------------------------------------- one queue, two schedules, one run at a time

class TestSingleFlight:
    """TWO SCHEDULES NOW FIRE THIS WORKER and they were racing.

    `MT5-Deepening` has run it hourly with `--limit 25` since 2026-09-03, and
    `hourly_cycle.deepen()` began draining the whole queue in-process on 2026-09-05. The
    worked-ledger stops a task being BILLED twice, but it cannot stop two concurrent runs from
    CHOOSING the same task -- both read the decided set before either appends -- and
    `OUT.write_text` is last-writer-wins, so the 25-task run can overwrite the whole-queue run's
    output with a fraction of it.

    A LOCK RATHER THAN A SCHEDULE CHANGE, deliberately: the Windows box's task registry is not in
    this repo, so a fix that depends on editing it is a fix that may never be applied.
    """

    def _lock_at(self, tmp_path, monkeypatch):
        p = tmp_path / ".deepening.lock"
        monkeypatch.setattr(dw, "LOCK", p)
        return p

    def test_a_second_run_refuses_rather_than_racing(self, tmp_path, monkeypatch) -> None:
        self._lock_at(tmp_path, monkeypatch)
        assert dw._single_flight() is not None
        assert dw._single_flight() is None, "two runs would choose the same tasks"

    def test_a_crashed_run_does_not_lock_the_desk_out_for_ever(self, tmp_path,
                                                               monkeypatch) -> None:
        """The failure mode of every naive lock file: the process dies mid-task, the file stays,
        and the organ is silently dark until a person notices. An unattended desk cannot wait."""
        import json as _json
        import time as _time
        p = self._lock_at(tmp_path, monkeypatch)
        p.write_text(_json.dumps({"pid": 1, "at": _time.time() - dw.RUN_BUDGET_SEC * 2 - 60}))
        assert dw._single_flight() is not None, "a stale lock was not taken over"

    def test_a_lock_inside_its_budget_is_respected(self, tmp_path, monkeypatch) -> None:
        """The threshold clears a legitimate long run: a pass may hold this for the whole run
        budget plus the task it was already inside when the budget expired."""
        import json as _json
        import time as _time
        p = self._lock_at(tmp_path, monkeypatch)
        p.write_text(_json.dumps({"pid": 1, "at": _time.time() - dw.RUN_BUDGET_SEC - 10}))
        assert dw._single_flight() is None, "a healthy long run was killed by the next tick"

    def test_an_unreadable_lock_is_a_dead_lock(self, tmp_path, monkeypatch) -> None:
        p = self._lock_at(tmp_path, monkeypatch)
        p.write_text("{not json")
        assert dw._single_flight() is not None

    def test_the_lock_is_released_even_when_the_work_raises(self, tmp_path, monkeypatch) -> None:
        """The one run whose lock most needs clearing is the one that died."""
        p = self._lock_at(tmp_path, monkeypatch)
        monkeypatch.setattr(dw, "_work", lambda argv=None: (_ for _ in ()).throw(RuntimeError("x")))
        with pytest.raises(RuntimeError):
            dw.main([])
        assert not p.exists(), "a crashed run left its lock behind"

    def test_a_lock_that_cannot_be_written_does_not_stop_the_work(self, tmp_path,
                                                                  monkeypatch) -> None:
        """The race it prevents is wasteful, not dangerous -- the worked-ledger still stops double
        billing -- so an unwritable path degrades to the previous behaviour, never to silence."""
        monkeypatch.setattr(dw, "LOCK", tmp_path / "nope" / "deep" / ".lock")
        monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
        assert dw._single_flight() is not None
