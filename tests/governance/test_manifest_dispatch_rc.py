"""The manifest dispatcher must record the EXIT CODE of every row it fires.

THE DEFECT (measured 2026-08-29). `scripts/run_manifest_dispatch.py` resurrects ~70 dead cron
rows under a user timer and detaches each one with stdout and stderr on ``DEVNULL``. Roughly
thirty of those rows are FENCES whose whole contract is to exit 2 on a real finding --
``check_organ_liveness`` was returning ``DARK`` with 32 dead organs, ``check_bar_span``
``CONTAMINATED`` across 88/88 series, ``check_calibration`` ``OVERDUE`` on 20 forecasts -- and
nothing anywhere collected an exit code. Every one of those verdicts existed only inside a log
file with no reader, so the desk learned a fence was red only when a human happened to run it by
hand. A fence that fails loud into a void is indistinguishable from one that passes, which is the
same false-GREEN class `libs/ops/fence_exit.py` was built to end, one layer further out.

WHAT THESE TESTS PIN, in the order the bug was actually found:
  1. a row that exits non-zero leaves an outcome row at all (the original defect recorded
     NOTHING, so downstream absence read as "not red");
  2. a row sealed with ``exit $?`` -- the house pattern that stops bash re-reading a rewritten
     script mid-run -- still records. The first version of the fix ran the row directly in the
     dispatcher's own shell, so an ``exit`` terminated the shell BEFORE the appender line and
     silently dropped exactly the rows most likely to be long-running;
  3. ``red_rows`` reports only non-zero, keeps the LATEST outcome per token (a fence that has
     since gone green must stop being reported) and honours its window.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "run_manifest_dispatch", _ROOT / "scripts" / "run_manifest_dispatch.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fire(mod: ModuleType, cmd: str, token: str, at: str) -> None:
    subprocess.run(["/bin/sh", "-c", mod._wrap_for_rc(cmd, token, at)],
                   cwd=str(_ROOT), check=False, timeout=60)


@pytest.fixture()
def dispatch(tmp_path: Path) -> ModuleType:
    """The module with its outcomes file redirected into tmp_path.

    The real `data/fence_outcomes.jsonl` is live evidence the running timer appends to; a test
    that wrote it would be recording fabricated fence verdicts into the desk's own record.
    """
    mod = _load()
    mod.OUTCOMES = tmp_path / "fence_outcomes.jsonl"
    return mod


def _rows(mod: ModuleType) -> list[dict[str, object]]:
    return [json.loads(line) for line in mod.OUTCOMES.read_text("utf-8").splitlines() if line]


def test_failing_row_records_its_exit_code(dispatch: ModuleType) -> None:
    _fire(dispatch, '.venv/bin/python -c "import sys; sys.exit(2)"',
          "scripts/red.py", "2026-08-29T05:00:00+00:00")
    rows = _rows(dispatch)
    assert len(rows) == 1, "a fired row must leave exactly one outcome"
    assert rows[0]["token"] == "scripts/red.py"
    assert rows[0]["rc"] == 2, "rc=2 is the desk-wide fence-failure code and must survive"


def test_sealed_exit_row_still_records(dispatch: ModuleType) -> None:
    """`exit $?` inside the row must end the ROW, never the recording."""
    _fire(dispatch, "exit 3", "scripts/sealed.py", "2026-08-29T05:00:00+00:00")
    rows = _rows(dispatch)
    assert rows and rows[0]["rc"] == 3, (
        "a row sealed with `exit` recorded nothing before the subshell fix, and a token with no "
        "outcome reads downstream as not-red -- absence mistaken for a clean verdict")


def test_passing_row_records_zero_and_is_not_red(dispatch: ModuleType) -> None:
    _fire(dispatch, "true", "scripts/green.py", "2026-08-29T05:00:00+00:00")
    assert _rows(dispatch)[0]["rc"] == 0
    now = datetime.fromisoformat("2026-08-29T05:10:00+00:00")
    assert dispatch.red_rows(now=now) == {}


def test_red_rows_keeps_latest_per_token(dispatch: ModuleType) -> None:
    """A fence that has since gone green stops being reported; the reverse also holds."""
    dispatch.OUTCOMES.write_text(
        '{"token":"scripts/a.py","at":"2026-08-29T01:00:00+00:00","rc":2}\n'
        '{"token":"scripts/a.py","at":"2026-08-29T04:00:00+00:00","rc":0}\n'
        '{"token":"scripts/b.py","at":"2026-08-29T01:00:00+00:00","rc":0}\n'
        '{"token":"scripts/b.py","at":"2026-08-29T04:00:00+00:00","rc":2}\n', "utf-8")
    reds = dispatch.red_rows(now=datetime.fromisoformat("2026-08-29T05:00:00+00:00"))
    assert set(reds) == {"scripts/b.py"}


def test_red_rows_honours_its_window(dispatch: ModuleType) -> None:
    dispatch.OUTCOMES.write_text(
        '{"token":"scripts/old.py","at":"2026-08-01T00:00:00+00:00","rc":2}\n', "utf-8")
    now = datetime.fromisoformat("2026-08-29T05:00:00+00:00")
    assert dispatch.red_rows(now=now) == {}
    assert set(dispatch.red_rows(within_h=24 * 365, now=now)) == {"scripts/old.py"}


def test_missing_outcomes_file_is_empty_not_an_error(dispatch: ModuleType) -> None:
    """UNMEASURED must not crash the dispatcher; the CALLER reports the file's own age."""
    assert dispatch.red_rows(now=datetime.now(UTC)) == {}


def test_malformed_line_does_not_poison_the_roll_up(dispatch: ModuleType) -> None:
    dispatch.OUTCOMES.write_text(
        "not json at all\n"
        '{"token":"scripts/c.py","at":"2026-08-29T04:00:00+00:00","rc":2}\n', "utf-8")
    reds = dispatch.red_rows(now=datetime.fromisoformat("2026-08-29T05:00:00+00:00"))
    assert set(reds) == {"scripts/c.py"}


def test_outcome_coverage_is_the_red_lists_denominator(dispatch: ModuleType) -> None:
    """`0 red` must be readable against how many rows actually reported.

    Without this count, a dispatcher that fired nothing and a fleet in which every fence passed
    produce the identical `red_rows_n: 0`, and the desk has already paid for that identity once
    (a frozen archive reported as an accruing clock for eight days).
    """
    now = datetime.fromisoformat("2026-08-29T05:00:00+00:00")
    assert dispatch.outcome_coverage(now=now) == 0, "no file at all is zero coverage, not zero red"
    dispatch.OUTCOMES.write_text(
        '{"token":"scripts/a.py","at":"2026-08-29T04:00:00+00:00","rc":0}\n'
        '{"token":"scripts/a.py","at":"2026-08-29T04:30:00+00:00","rc":0}\n'
        '{"token":"scripts/b.py","at":"2026-08-29T04:00:00+00:00","rc":2}\n'
        '{"token":"scripts/stale.py","at":"2026-08-01T04:00:00+00:00","rc":0}\n', "utf-8")
    assert dispatch.outcome_coverage(now=now) == 2, "DISTINCT tokens inside the window"
    assert len(dispatch.red_rows(now=now)) == 1
