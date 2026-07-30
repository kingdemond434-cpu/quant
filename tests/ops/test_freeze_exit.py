"""The freeze-exit gate must be STRICT, not UNSATISFIABLE -- and those look identical from outside.

On 2026-07-30 three of the five lockdown-exit criteria read filenames nothing in this repo writes
(`fills.csv`, `weekly_cost_summary.json`, `calibration.csv`), and a fourth was logically inverted:
`fills_4wk` compared `now - file_mtime > 28 days`, which reads "this feed has been DEAD for a
month". A healthy, actively-appended fill feed failed forever; only an abandoned one could pass.

The desk's entire research apparatus funnels into this gate. It was not merely unmet, it was
unmeetable -- and the only place that was stated was a status string with one writer and zero
readers. These tests pin both halves: the criteria read real artifacts, and the fills clock counts
UP with a live feed rather than rewarding a dead one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
import scripts.run_cadence as C


def test_every_criterion_reads_an_artifact_something_writes():
    """THE GENERALISED FENCE. A criterion whose artifact has no writer reads False forever, which
    is indistinguishable from 'not earned yet' -- so the gate looks strict while being
    unsatisfiable. This checks the WRITER, not the artifact: pre-launch the artifacts are
    legitimately absent, but their producer must exist today."""
    assert C.check_freeze_exit_sources() == []


def test_the_five_criteria_are_all_mapped():
    """A criterion missing from _FREEZE_SOURCES is one nobody has to justify."""
    _, why = C._freeze_exit_met()
    reported = {kv.split("=")[0] for kv in why.split(", ")}
    assert reported == set(C._FREEZE_SOURCES), (
        f"criteria evaluated {reported} != criteria mapped {set(C._FREEZE_SOURCES)}")


def test_no_criterion_reads_one_of_the_phantom_filenames():
    """A regression fence naming the three specific invented files, so re-introducing any of them
    fails loudly rather than quietly re-freezing the desk."""
    import ast
    import inspect

    # EXECUTABLE CODE ONLY. The function's docstring names all three phantoms on purpose -- that
    # is the record of what went wrong and why. Stripping docstrings is what makes this fence
    # check behaviour rather than prose, and keeps the explanation from tripping its own alarm.
    tree = ast.parse(inspect.getsource(C._freeze_exit_met).strip())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            node.value.value = ""
    body = ast.unparse(tree)
    for phantom in ("fills.csv", "weekly_cost_summary.json", "calibration.csv"):
        assert phantom not in body, (
            f"{phantom} has no writer in this repo -- that criterion would be "
            "unmeetable, not strict")


class TestFillsClockIsNotInverted:
    """`fills_4wk` must count UP as a live feed accrues history, never reward an abandoned one."""

    def _tape(self, tmp_path, *, span_days: float, n: int):
        p = tmp_path / "tape.jsonl"
        last = datetime.now(tz=UTC)
        first = last - timedelta(days=span_days)
        rows = []
        for i in range(n):
            t = first + (last - first) * (i / max(n - 1, 1))
            rows.append(json.dumps({"opened": t.isoformat(), "closed": t.isoformat()}))
        p.write_text("\n".join(rows) + "\n", "utf-8")
        return p

    @pytest.mark.parametrize(("span", "n", "expected"), [
        (26.42, 517, False),   # the desk's real 2026-07-30 position: 1.58 days short
        (28.01, 517, True),    # just over the bar
        (60.0, 517, True),     # well over
        (60.0, 10, False),     # long span, too few fills -- depth matters as well as duration
    ])
    def test_coverage_days_drive_the_criterion(self, tmp_path, span, n, expected):
        from libs.execution.execution_tape import coverage
        cov = coverage(path=self._tape(tmp_path, span_days=span, n=n))
        met = float(cov["days"]) >= 28.0 and int(cov["n"]) > 50
        assert met is expected, f"span={span}d n={n} -> {cov}"

    def test_a_freshly_written_tape_is_not_penalised_for_being_fresh(self, tmp_path):
        """THE INVERSION, pinned. The old check used file mtime, so writing the file NOW made it
        fail. Row timestamps are what matter: a tape written this second but spanning 40 days of
        history is 40 days of evidence."""
        from libs.execution.execution_tape import coverage
        p = self._tape(tmp_path, span_days=40.0, n=200)
        assert p.stat().st_mtime > (datetime.now(tz=UTC) - timedelta(minutes=1)).timestamp()
        cov = coverage(path=p)
        assert float(cov["days"]) >= 28.0, "a just-written tape with 40d of rows must pass"

    def test_an_abandoned_tape_gains_nothing_from_being_stale(self, tmp_path):
        """The other half of the inversion: under the old logic, ABANDONING the feed for 29 days
        was the only way to pass. A short-span tape must stay failing however old the file is."""
        import os

        from libs.execution.execution_tape import coverage
        p = self._tape(tmp_path, span_days=5.0, n=200)
        old = (datetime.now(tz=UTC) - timedelta(days=90)).timestamp()
        os.utime(p, (old, old))
        cov = coverage(path=p)
        assert float(cov["days"]) < 28.0, "5 days of rows is 5 days of evidence at any file age"


def test_status_is_written_every_cycle_not_only_on_failure(tmp_path, monkeypatch):
    """It used to be set only in the else-branch, into a key with one writer and zero readers.
    A gate whose verdict is unreadable is a gate nobody can act on."""
    src = (C._ROOT_DIR / "scripts/run_cadence.py").read_text("utf-8")
    block = src[src.index("# FREEZE-EXIT (deterministic"):]
    block = block[:block.index("_assert_floors")]
    assert "_FREEZE_STATUS.write_text" in block, "the verdict must reach an artifact"
    assert block.index('state["freeze_exit_status"] = why') < block.index("if met:"), (
        "status must be recorded BEFORE the met/not-met branch, so success is logged too")
