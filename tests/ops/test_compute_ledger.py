"""Compute is costed, and the ranking refuses to invent the value it divides.

WHY THE DENOMINATOR IS THE WHOLE POINT. The compute allocator ranks by value per hour, and this
desk had never recorded an hour: every run's cost was unknown, so the formula had nothing to
divide by. Shipping the ranking against an absent denominator would have produced a confident
ordering of made-up numbers -- strictly worse than the arrival order it replaced, because it
would have looked principled. So this module records cost and reads it back, and `rank` refuses
any run whose value it was not given.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.ops import compute_ledger as cl


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch) -> Path:
    p = tmp_path / "compute_ledger.jsonl"
    monkeypatch.setattr(cl, "LEDGER", p)
    return p


class TestEveryRunLeavesItsCost:
    def test_a_completed_block_records_wall_and_cpu(self, ledger) -> None:
        with cl.costed("mine", kind="hourly_cycle") as r:
            r["rows"] = 42
        (row,) = cl.rows(path=ledger)
        assert row["run"] == "mine" and row["outcome"] == "ok"
        assert row["wall_s"] >= 0.0 and "cpu_s" in row
        assert row["rows"] == 42, "the caller's own result must ride on the row"

    def test_a_raising_block_still_records_and_names_the_failure(self, ledger) -> None:
        """AN EXPENSIVE FAILURE IS THE MOST VALUABLE ROW IN A COMPUTE LEDGER and the easiest to
        lose. A run that burned forty minutes and crashed burned forty minutes."""
        with pytest.raises(ValueError), cl.costed("deepen", kind="seat"):
            raise ValueError("seat 429")
        (row,) = cl.rows(path=ledger)
        assert row["run"] == "deepen"
        assert "ValueError" in row["outcome"] and "429" in row["outcome"]

    def test_the_exception_still_propagates(self, ledger) -> None:
        """A ledger that swallowed the error would turn a crash into a silent no-op."""
        with pytest.raises(KeyError), cl.costed("x"):
            raise KeyError("boom")

    def test_a_ledger_write_never_takes_down_the_work(self, tmp_path, monkeypatch) -> None:
        """A measurement that can break the thing it measures gets removed within a week, and
        correctly. An unwritable path must cost the run nothing."""
        monkeypatch.setattr(cl, "LEDGER", tmp_path / "nope" / "x" / "l.jsonl")
        monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
        with cl.costed("mine") as r:
            r["ok"] = True
        assert r["ok"] is True


class TestWhatAccumulates:
    def test_costs_and_failure_rate_aggregate_by_run(self, ledger) -> None:
        """THE FAILURE RATE RIDES WITH THE COST because they are one decision: a forty-minute run
        that fails a third of the time costs sixty minutes per useful pass."""
        for outcome in ("ok", "ok", "TimeoutError: mt5"):
            run = cl.open_run("sweep")
            cl.close_run(run, outcome=outcome)
        agg = cl.cost_by_run(path=ledger)["sweep"]
        assert agg["runs"] == 3 and agg["failures"] == 1
        assert agg["failure_rate"] == pytest.approx(1 / 3, abs=1e-4)

    def test_a_missing_ledger_is_an_empty_list_not_a_zero(self, tmp_path) -> None:
        """The caller must be able to tell 'nothing has been costed' from 'everything cost
        nothing' -- one is a wiring state and the other is a measurement."""
        assert cl.rows(path=tmp_path / "absent.jsonl") == []
        out = cl.rank({}, path=tmp_path / "absent.jsonl")
        assert out["costed_runs"] == 0 and "no denominator" in out["why"]

    def test_rows_outside_the_window_are_not_ranked(self, ledger) -> None:
        """A value-per-hour estimate from a run whose code no longer exists prices a different
        program."""
        ledger.write_text('{"at": "2020-01-01T00:00:00+00:00", "run": "old", "wall_s": 99}\n',
                          "utf-8")
        assert cl.rows(path=ledger) == []

    def test_a_corrupt_line_does_not_lose_the_rest_of_the_file(self, ledger) -> None:
        run = cl.open_run("good")
        cl.close_run(run)
        with open(ledger, "a", encoding="utf-8") as fh:
            fh.write("{not json\n")
        assert [r["run"] for r in cl.rows(path=ledger)] == ["good"]


class TestTheRankingRefusesToInventItsNumerator:
    def test_a_costed_run_with_no_value_is_unpriced_not_ranked(self, ledger) -> None:
        """Inventing a numerator to sit over a real denominator is how a compute allocator becomes
        a confident ordering of made-up numbers."""
        cl.close_run(cl.open_run("mine"))
        out = cl.rank({}, path=ledger)
        assert out["ranked"] == [] and out["unpriced"] == ["mine"]

    def test_a_valued_run_with_no_cost_is_uncosted_and_named(self, ledger) -> None:
        cl.close_run(cl.open_run("mine"))
        out = cl.rank({"mine": 0.001, "never_run": 0.005}, path=ledger)
        assert "never_run" in out["uncosted"]

    def test_runs_are_ordered_by_value_per_hour_not_by_value(self, ledger) -> None:
        """The entire point of the level: a cheap small win can beat an expensive large one."""
        import json
        ledger.write_text("\n".join(json.dumps(r) for r in [
            {"at": cl.datetime.now(cl.UTC).isoformat(), "run": "cheap", "wall_s": 3600.0,
             "outcome": "ok"},
            {"at": cl.datetime.now(cl.UTC).isoformat(), "run": "dear", "wall_s": 36000.0,
             "outcome": "ok"},
        ]) + "\n", "utf-8")
        out = cl.rank({"cheap": 0.001, "dear": 0.005}, path=ledger)
        assert [r["run"] for r in out["ranked"]] == ["cheap", "dear"]
        assert out["ranked"][0]["value_per_hour"] > out["ranked"][1]["value_per_hour"]


def test_the_hourly_cycle_costs_every_leg() -> None:
    """A ledger nothing writes to is the defect in a new costume, and this desk has shipped that
    twice today. The hourly cycle is where most of the desk's compute is actually spent, so its
    legs are the denominator -- no new schedule, no new process, one append per leg."""
    src = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
           / "hourly_cycle.py").read_text("utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "from libs.ops.compute_ledger import close_run, open_run" in code
    for leg in ("health", "record_tape", "state_vector", "daily", "deepen", "heal_clocks", "mine"):
        assert f'_costed("{leg}"' in code, f"the {leg} leg runs uncosted"
