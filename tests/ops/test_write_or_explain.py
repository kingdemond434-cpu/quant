"""THE WRITE-OR-EXPLAIN CONTRACT's own tests.

The contract exists because eight failures on 2026-09-23 were all silent, so these tests are
mostly about the three sentences it is allowed to pass: it must say OK only when bytes moved,
DECLARED_NO_OP only when the leg actually named a reason, and SILENT_NO_OP for everything else
that exited clean. The most important test in the file is
`test_generic_note_does_not_launder_silence`: if a leg can buy a pass with a field it was already
filling for another purpose, the contract reads green on exactly the organs it was built to catch.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import write_or_explain as woe

ROOT = Path(__file__).resolve().parents[2]


def _snap(exists: bool, mtime: int = 0, size: int = -1) -> dict[str, dict[str, object]]:
    return {"a.json": {"exists": exists, "mtime_ns": mtime, "size": size}}


ABSENT = _snap(False)
PRESENT = _snap(True, 100, 10)


def test_ok_only_when_the_artifact_moved() -> None:
    assert woe.judge("leg", ABSENT, PRESENT, {"exit_code": 0})["verdict"] == woe.OK
    assert woe.judge("leg", PRESENT, _snap(True, 200, 10), {"exit_code": 0})["verdict"] == woe.OK
    # same mtime, different size: a rewrite the clock was too coarse to see
    assert woe.judge("leg", PRESENT, _snap(True, 100, 11), {"exit_code": 0})["verdict"] == woe.OK


def test_silent_no_op_is_its_own_verdict() -> None:
    """Failure 2: `producer_census` exited rc=0 in ZERO seconds and wrote nothing."""
    rec = woe.judge("producer_census", ABSENT, ABSENT, {"exit_code": 0, "tail": "done"},
                    wall_s=0.0)
    assert rec["verdict"] == woe.SILENT_NO_OP
    assert "producer_census" in rec["detail"]
    assert "a.json" in rec["detail"]


def test_non_zero_exit_is_loud_and_carries_the_code_and_stderr() -> None:
    """Failure 3: `coverage_tensor` exited 1 on every pass and its artifact never existed."""
    rec = woe.judge("coverage_tensor", ABSENT, ABSENT,
                    {"exit_code": 1, "stderr_tail": "Traceback\nKeyError: 'families'"})
    assert rec["verdict"] == woe.LEG_FAILED
    assert "exited 1" in rec["detail"]
    assert "KeyError" in rec["stderr_tail"]


def test_a_leg_that_raised_is_never_swallowed() -> None:
    rec = woe.judge("leg", ABSENT, ABSENT, None, raised="RuntimeError: boom")
    assert rec["verdict"] == woe.LEG_FAILED
    assert "RuntimeError" in rec["stderr_tail"]


def test_declared_no_op_needs_a_named_reason() -> None:
    rec = woe.judge("leg", ABSENT, ABSENT,
                    {"exit_code": 0, "noop_reason": "0 new donations since cursor 4821"})
    assert rec["verdict"] == woe.DECLARED_NO_OP
    assert "cursor 4821" in rec["reason"]


def test_a_subprocess_leg_declares_a_no_op_with_one_printed_line() -> None:
    rec = woe.judge("leg", ABSENT, ABSENT,
                    {"exit_code": 0, "tail": "ran\nWRITE_OR_EXPLAIN: NO_OP nothing upstream\n"})
    assert rec["verdict"] == woe.DECLARED_NO_OP
    assert "nothing upstream" in rec["reason"]


@pytest.mark.parametrize("payload", [
    {"exit_code": 0, "note": "ran fine"},
    {"exit_code": 0, "reason": "see above"},
    {"exit_code": 0, "why": "because"},
    {"exit_code": 0, "detail": "12 rows examined"},
])
def test_generic_note_does_not_launder_silence(payload: dict[str, object]) -> None:
    """THE LOAD-BEARING TEST. Dozens of legs already return a `note`/`why`/`reason` about
    something unrelated. If those counted as a declaration, every one of them would buy a pass it
    never earned -- and the contract would read green on precisely the organs it was built for.
    A no-op is declared on purpose, or it is not declared."""
    assert woe.judge("leg", ABSENT, ABSENT, payload)["verdict"] == woe.SILENT_NO_OP


def test_generic_fields_count_only_when_the_status_says_no_op() -> None:
    rec = woe.judge("leg", ABSENT, ABSENT,
                    {"exit_code": 0, "status": "NOOP", "why": "no donations this pass"})
    assert rec["verdict"] == woe.DECLARED_NO_OP
    assert "no donations" in rec["reason"]


def test_a_verdict_exit_cannot_buy_silence() -> None:
    """A declared verdict exit is judged on whether it WROTE, exactly like a clean exit. An organ
    must be able to report bad news without failing the cycle -- not to stop reporting at all."""
    assert woe.judge("leg", ABSENT, PRESENT, {"exit_code": 2},
                     verdict_exits=(2,))["verdict"] == woe.OK
    assert woe.judge("leg", ABSENT, ABSENT, {"exit_code": 2},
                     verdict_exits=(2,))["verdict"] == woe.SILENT_NO_OP


def test_timeout_and_missing_script_are_defects_not_passes() -> None:
    assert woe.judge("leg", ABSENT, ABSENT,
                     {"exit_code": None, "timeout_s": 720})["verdict"] == woe.LEG_TIMEOUT
    assert woe.judge("leg", ABSENT, ABSENT,
                     {"exit_code": None, "status": "MISSING",
                      "why": "no such script"})["verdict"] == woe.LEG_FAILED


def test_skipped_by_plan_is_not_judged() -> None:
    assert woe.judge("leg", ABSENT, ABSENT,
                     {"status": "SKIPPED_BY_PLAN"})["verdict"] == woe.SKIPPED


def test_undeclared_is_reported_and_is_not_a_pass() -> None:
    rec = woe.judge("leg", {}, {}, {"exit_code": 0})
    assert rec["verdict"] == woe.UNDECLARED
    assert rec["verdict"] not in woe.DEFECTS      # reported, not a defect
    assert rec["verdict"] not in woe.PASSING      # ...and never counted as clean either


def test_declared_artifacts_are_not_filtered_by_existence() -> None:
    """THE LINE THAT MADE FAILURE 3 INVISIBLE. `hourly_cycle._leg_artifacts` drops a declared
    artifact that does not exist, so the one organ that had NEVER succeeded declared nothing and
    could not be caught failing to write. An absent artifact is the signal, not a reason to look
    away."""
    table = woe.leg_table()
    assert table, "the leg registry declares no artifacts at all"
    leg = next(iter(table))
    paths = woe.declared_artifacts(leg)
    assert paths, f"{leg} declares {table[leg]} but resolved to nothing"
    missing = [p for p in paths if not p.exists()]
    for p in missing:                             # a declared home is returned regardless
        assert p.is_absolute()


def test_artifact_declarations_that_are_prose_still_yield_their_paths() -> None:
    """122 of the 243 hourly legs declare their artifact as something other than a bare path.
    Treating the whole string as a filename would give half the desk a path that can never exist
    and mark every one of them SILENT_NO_OP forever."""
    assert woe.artifact_paths("desks/mt5/reports/MODEL_ZOO.json generator_entrants") == [
        "desks/mt5/reports/MODEL_ZOO.json"]
    assert woe.artifact_paths("a/b.jsonl + c/d.jsonl + e/f.json") == [
        "a/b.jsonl", "c/d.jsonl", "e/f.json"]
    assert woe.artifact_paths(
        "desks/mt5/reports/pf_allocation.json (`objective_terms`: cost_of_w, tiers)") == [
        "desks/mt5/reports/pf_allocation.json"]
    # LONGEST EXTENSION FIRST: `json|jsonl` truncated `task_queue.jsonl` to a path that is not
    # there, for a leg that writes perfectly well.
    assert woe.artifact_paths("desks/mt5/data/task_queue.jsonl") == [
        "desks/mt5/data/task_queue.jsonl"]
    # a GLOB names a pattern, not a file; statting it would manufacture a permanent false defect
    assert woe.artifact_paths("desks/mt5/data/.job_locks/*.peaks.json") == []
    assert woe.artifact_paths("no path at all here") == []


def test_every_declared_path_is_relative_and_extensioned() -> None:
    for leg, paths in woe.leg_table().items():
        assert paths, f"{leg} kept an empty declaration"
        for p in paths:
            assert not p.startswith("/") and ":" not in p, f"{leg}: {p} is not repo-relative"
            assert "." in Path(p).name, f"{leg}: {p} has no extension"
            assert "*" not in p, f"{leg}: {p} is a glob"


def test_the_suite_never_writes_into_the_desk_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    """R0748. `test_hourly_cycle_legs_are_callable` drives `_costed` with simulated failing legs;
    without this guard the suite appends phantom legs to the box's own contract ledger and the
    fence then reports them as real defects. Measured: it did exactly that."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
    monkeypatch.delenv("WRITE_OR_EXPLAIN_LEDGER", raising=False)
    assert woe.record({"leg": "phantom"}) is False


def test_the_defect_and_passing_sets_do_not_overlap() -> None:
    assert not (woe.DEFECTS & woe.PASSING)
    assert woe.SILENT_NO_OP in woe.DEFECTS
    assert woe.NEVER_OBSERVED in woe.DEFECTS


def test_observe_records_a_row_and_never_raises(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "woe.jsonl"
    monkeypatch.setattr(woe, "LEDGER", ledger)
    monkeypatch.setenv("WRITE_OR_EXPLAIN_LEDGER", str(ledger))   # the opt-in the guard documents
    rec = woe.observe("some_leg", ABSENT, {"exit_code": 0})
    assert rec["recorded"] is True
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows and rows[-1]["leg"] == "some_leg"
    # an unserialisable result must still produce a row rather than an exception
    assert woe.observe("some_leg", ABSENT, object())["verdict"] in (
        woe.SILENT_NO_OP, woe.UNDECLARED, woe.LEG_FAILED)


def test_record_returns_false_instead_of_raising_when_the_ledger_cannot_be_written(
        tmp_path: Path) -> None:
    """An organ that dies because its telemetry failed is worse than one that runs untelemetered."""
    blocked = tmp_path / "a_file"
    blocked.write_text("not a directory", encoding="utf-8")
    assert woe.record({"leg": "x"}, ledger=blocked / "nested" / "woe.jsonl") is False


def test_both_cycles_call_the_contract_at_their_leg_boundary() -> None:
    """UNWIRED IS A DEFECT (III.16). The contract is only worth anything at the one boundary
    every leg passes through, so the wiring is pinned in both runners by name."""
    hourly = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(
        encoding="utf-8", errors="replace")
    costed = hourly.split("def _costed(", 1)[1].split("\ndef ", 1)[0]
    assert "_woe_before(name)" in costed
    assert "_woe_after(" in costed
    daily = (ROOT / "desks" / "mt5" / "research" / "daily_cycle.py").read_text(
        encoding="utf-8", errors="replace")
    step = daily.split("def run_step(", 1)[1].split("\ndef ", 1)[0]
    assert "_woe_before(name)" in step
    assert "_woe_after(" in step


def test_the_producer_keeps_stderr_so_a_failure_can_be_loud() -> None:
    """`tail` is `stdout or stderr`, so a leg that printed anything before dying lost its
    traceback entirely -- which is why `coverage_tensor` exiting 1 never told anyone why."""
    hourly = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(
        encoding="utf-8", errors="replace")
    assert '"stderr_tail": (r.stderr or "")' in hourly


def test_the_fences_are_registered_in_the_law_gate() -> None:
    """A fence with no clock is a claim the desk cannot cash (L1.49)."""
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8", errors="replace")
    assert '("check_write_or_explain.py", ("--wiring-only",))' in gate
    assert '("check_write_or_explain.py", ("--require-state",))' in gate
    assert '("check_box_reversion.py", ("--require-git",))' in gate
    assert '("check_bare_excepts.py", ("--file-writes-only",))' in gate
