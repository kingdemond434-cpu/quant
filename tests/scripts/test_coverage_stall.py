"""L1.50 -- A FLOOR THAT HAS NOT RISEN IS A RATCHET THAT HAS STOPPED.

The ratchet failed on REGRESSION and was silent on STAGNATION. A desk measuring 89.06% every day
for a year is permanently green and permanently unimproved, and the instrument built to force
improvement reports success throughout. That is L1.49's shape one level up: not a gate that never
ran, but a gate that runs, passes, and asks nothing.

THE TWO WAYS THIS FEATURE COULD BE BUILT WRONG, both tested below, because both would leave a
check that looks like it works:

  1. `last_raised` stamped on every `--update` run. Then running the updater is indistinguishable
     from improving coverage, and the stall detector reports health in exchange for being invoked.
     That is GAP #85 exactly -- an `n` counting READINGS OF THE WORLD rather than events in it, so
     diligence in running the audit becomes the mechanism by which the audit goes wrong.
  2. A missing `last_raised` treated as 0 days. Then the OLDEST records -- the ones written before
     this law existed, the ones most likely to be stalled -- get the healthiest possible reading.
     That is GAP #83 exactly, where a register never driven once scored perfect because -1.0 fails
     every `age > bar` comparison.

And the third property, which is a design choice rather than a bug: STALLING MUST NOT EXIT
NON-ZERO. A check that goes red on a quiet day gets deleted, and a deleted check enforces nothing.
Regression is CI's business; stagnation is the auditor's.
"""

from __future__ import annotations

import contextlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import scripts.check_coverage_floors as C


def _report(repo: float = 90.0, money: float = 60.0) -> dict[str, Any]:
    """A coverage.py JSON report shaped like the real one, with one money-path file."""
    return {
        "totals": {"percent_covered": repo},
        "files": {
            C.MONEY_PATH[0]: {"summary": {"num_statements": 1000, "covered_lines": int(money * 10)}}
        },
    }


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rec: dict[str, Any],
    report: dict[str, Any],
    *,
    update: bool = False,
) -> tuple[int, str, dict[str, Any]]:
    """Drive main() against an isolated record; return (exit code, stdout, record after)."""
    rpath = tmp_path / "coverage.json"
    rpath.write_text(json.dumps(report), "utf-8")
    recpath = tmp_path / "COVERAGE_RATCHET.json"
    recpath.write_text(json.dumps(rec), "utf-8")
    monkeypatch.setattr(C, "RECORD", recpath)
    argv = ["check_coverage_floors.py", "--report", str(rpath)] + (["--update"] if update else [])
    monkeypatch.setattr("sys.argv", argv)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = C.main()
    after = json.loads(recpath.read_text("utf-8"))
    return code, buf.getvalue(), after


def _rec(repo: float, money: float, raised: str | None) -> dict[str, Any]:
    return {
        "high_water": {"repo_pct": repo, "money_path_pct": money},
        **({"last_raised": raised} if raised is not None else {}),
    }


def test_measure_normalizes_windows_coverage_paths() -> None:
    report = _report(repo=93.0, money=75.0)
    details = report["files"].pop(C.MONEY_PATH[0])
    report["files"][C.MONEY_PATH[0].replace("/", "\\")] = details

    measured = C.measure(report)

    assert measured["repo_pct"] == 93.0
    assert measured["money_path_pct"] == 75.0
    assert measured["money_path_statements"] == 1000


# ------------------------------------------------------------------ the stall itself


def test_A_LONG_QUIET_RATCHET_IS_REPORTED_AS_STALLED(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The whole point. Floors holding is the MINIMUM; it is not the target, and an instrument
    that says only "both floors held" lets a permanently-green desk read as a finished one."""
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, old), _report(90.0, 60.0))
    assert "STALL" in out and "40 days" in out
    assert code == 0, "stagnation must REPORT, never block -- a check that reddens quiet days dies"


def test_A_RECENT_RAISE_IS_NOT_A_STALL(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The other half of the bar. A detector that fires always is not a detector."""
    recent = (datetime.now(tz=UTC) - timedelta(days=2)).isoformat()
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, recent), _report())
    assert "STALL" not in out
    assert "ratchet moving" in out


def test_A_MISSING_TIMESTAMP_IS_NOT_A_CLEAN_READING(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GAP #83's shape. Every record written before this law has no `last_raised`, and those are
    precisely the records most likely to be stalled. If absence read as "raised today" the oldest
    records would score healthiest -- absence of evidence rendered as evidence of compliance, on
    the instrument whose entire job is to notice that nothing is happening."""
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report())
    assert "STALL" in out
    assert "never recorded a raise" in out


@pytest.mark.parametrize("bad", ["", "not-a-date", "2026-08-06T00:00:00"])
def test_AN_UNPARSEABLE_OR_NAIVE_STAMP_IS_ALSO_NOT_CLEAN(monkeypatch, tmp_path, bad: str) -> None:  # type: ignore[no-untyped-def]
    """A NAIVE datetime is in the list deliberately. It parses fine and then compares wrong against
    every aware timestamp in this repo -- max_audit carries a dedicated check for exactly this --
    so accepting it would produce a confident number computed from an incomparable pair. Refusing
    to grade is the correct answer to input that cannot be compared (L1.28a)."""
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, bad), _report())
    assert "STALL" in out


# ------------------------------------------------- the stamp must track the world, not the auditor


def test_UPDATE_WITHOUT_A_RAISE_DOES_NOT_TOUCH_THE_STAMP(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """GAP #85's shape, and the single most important test here. If `--update` stamped
    `last_raised` unconditionally, then RUNNING THE UPDATER would be indistinguishable from
    IMPROVING COVERAGE -- the stall detector would report health in exchange for being invoked, and
    a desk could clear this law forever by scheduling a cron job."""
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    # measured EQUALS the floors: nothing rose.
    _code, out, after = _run(
        monkeypatch, tmp_path, _rec(90.0, 60.0, old), _report(90.0, 60.0), update=True
    )
    assert after["last_raised"] == old, "the updater stamped a raise that did not happen"
    assert "no raise" in out


def test_A_REAL_RAISE_MOVES_THE_STAMP_AND_THE_FLOOR(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    _code, out, after = _run(
        monkeypatch, tmp_path, _rec(89.06, 59.59, old), _report(91.0, 62.0), update=True
    )
    assert after["last_raised"] != old
    assert after["high_water"]["repo_pct"] == 91.0
    assert after["high_water"]["money_path_pct"] == 62.0
    assert "RAISED" in out


def test_A_RAISE_ON_EITHER_FLOOR_ALONE_COUNTS(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The money path is tracked separately precisely because a repo-wide average hides it. Moving
    it while the aggregate sits still is real progress -- arguably the most valuable kind here --
    and must not be recorded as a stall."""
    old = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    _code, _out, after = _run(
        monkeypatch, tmp_path, _rec(90.0, 59.59, old), _report(90.0, 62.0), update=True
    )
    assert after["last_raised"] != old
    assert after["high_water"]["repo_pct"] == 90.0, "the untouched floor must not move"


def test_FLOORS_STILL_NEVER_FALL(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The original guarantee, re-asserted because this change edited the --update branch: a
    measurement BELOW the mark must not lower it. A floor edited to fit the measurement is not a
    floor."""
    _code, _out, after = _run(
        monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(70.0, 30.0), update=True
    )
    assert after["high_water"]["repo_pct"] == 89.06
    assert after["high_water"]["money_path_pct"] == 59.59


# ------------------------------------------------------------ regression still fails, stall never


def test_REGRESSION_STILL_EXITS_NONZERO(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The bar for this whole change: adding a soft signal must not have softened the hard one."""
    code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(70.0, 30.0))
    assert code == 1
    assert "BREACH" in out and "MONEY PATH" in out


def test_THE_SLACK_BAND_IS_NOT_A_BREACH(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Coverage moves with test ordering and optional-dependency skips. A floor that fires on noise
    gets deleted, which is worse than a floor set one point low."""
    code, _out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(88.5, 59.0))
    assert code == 0


# --------------------------------------------------------------- the target is printed every run


def test_THE_DISTANCE_TO_100_IS_ALWAYS_REPORTED(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A floor is a MINIMUM and the target is 100%. Printing only the floor is how "both floors
    held" comes to sound like completion. The money-path residue is additionally rendered in
    STATEMENTS, not just percentage points, because "+40pp" is an abstraction and "~400 uncovered
    statements on the code that can move funds" is a work item."""
    _code, out, _ = _run(monkeypatch, tmp_path, _rec(89.06, 59.59, None), _report(90.0, 60.0))
    assert "to 100%" in out
    assert "+10.00pp" in out and "+40.00pp" in out
    assert "uncovered statements" in out


def test_days_since_REFUSES_RATHER_THAN_GUESSES() -> None:
    """Unit bar on the helper, since every caller's correctness rests on None meaning NOT MEASURED
    rather than zero."""
    assert C.days_since(None) is None
    assert C.days_since("") is None
    assert C.days_since("2026-08-06T00:00:00") is None, "naive stamps compare wrong -- refuse"
    fresh = C.days_since(datetime.now(tz=UTC).isoformat())
    assert fresh is not None and fresh < 0.01
    future = C.days_since((datetime.now(tz=UTC) + timedelta(days=5)).isoformat())
    assert future == 0.0, "a clock skew into the future must clamp, never report negative age"
