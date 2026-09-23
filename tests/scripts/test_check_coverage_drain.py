"""THE COVERAGE-DRAIN FENCE, VALIDATED -- the ratchet must hold, and must not hold too hard.

The fence has exactly two ways to be useless and this suite pins both.

  * TOO LOOSE: it passes while the desk falls further behind the ground it already owns. The
    overdue backlog rising, the OVERDUE part of the wait rising, or the cumulative drained count
    falling are each a FAIL, and none of them is a band -- a rise of one is a rise.
  * TOO TIGHT: it fails when the drain does its job. The organ's FIRST duty is to register
    lawful ground the registry had never heard of, which RAISES the headline uncrawled count.
    A fence that failed on that would teach the next session to stop seeding, and the desk would
    report a beautiful backlog of zero while knowing less every week. `test_a_rise_after_seeding`
    is the test that stops that being "fixed" by a later reviewer.

  * UNSATISFIABLE, which is a third way and the one this fence actually fell into: its first
    version ratcheted the RAW oldest wait, which rises with the clock whatever the drain does,
    and it went red on the third live pass for a queue entirely inside its own lease.
    `test_the_raw_oldest_wait_is_published_and_fails_nothing` is the record of that.

Plus the three the desk keeps breaking everywhere else: UNMEASURED is a verdict rather than a
pass, a ratchet with no history enters at what was MEASURED rather than at an invented zero, and
a stale report is a SCHEDULE defect named as such rather than counted as a worse number.

Nothing here reads or writes the live report or the live ledger: every test builds both in
`tmp_path` and points the fence at them.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_coverage_drain as F  # type: ignore[import-not-found]  # noqa: E402


def _iso(hours_ago: float = 0.0) -> str:
    return (datetime.now(tz=UTC) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def _report(tmp_path: Path, **measured: Any) -> Path:
    """A drain report with a `measured` block, the shape the organ actually writes."""
    seeded = measured.pop("seeded_this_pass", 0)
    at = measured.pop("at", None) or _iso()
    doc = {
        "at": at, "organ": "coverage_drain", "status": "MEASURED",
        "seeded_this_pass": seeded,
        "measured": {"backlog_overdue": 40, "oldest_wait_h": 124.0, "overdue_wait_h": 100.0,
                     "uncrawled_total": 200, "drained_total": 500.0, **measured},
        "backlog": {"uncrawled_total": measured.get("uncrawled_total", 200)},
        "verdict": {"gap": "OVERDUE_UNCRAWLED_SOURCES", "ev": 40.0, "what": "x", "fix": "y"},
    }
    path = tmp_path / "COVERAGE_DRAIN.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _ledger(tmp_path: Path, **kw: Any) -> Path:
    doc = {"at": _iso(1.0),
           "ceilings": {"backlog_overdue": 40.0, "overdue_wait_h": 100.0,
                        "uncrawled_total": 200.0},
           "floors": {"drained_total": 500.0}}
    for key, value in kw.items():
        if key in ("backlog_overdue", "overdue_wait_h", "uncrawled_total"):
            doc["ceilings"][key] = value
        else:
            doc["floors"][key] = value
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


# ------------------------------------------------------------------------------ the happy path
def test_a_steady_pass_passes(tmp_path: Path) -> None:
    got = F.judge(report=_report(tmp_path), ledger=_ledger(tmp_path))
    assert got["verdict"] == "PASS", got["reasons"]
    assert got["reasons"] == []


def test_a_falling_backlog_passes_and_says_so(tmp_path: Path) -> None:
    got = F.judge(report=_report(tmp_path, backlog_overdue=5, overdue_wait_h=3.0),
                  ledger=_ledger(tmp_path))
    assert got["verdict"] == "PASS"
    rows = {r["metric"]: r for r in got["checks"]}
    assert rows["backlog_overdue"]["state"] == "OK"
    assert "5.0 <= ceiling 40.0" in rows["backlog_overdue"]["why"]


# ---------------------------------------------------------------------------- the failing half
def test_a_rising_overdue_backlog_fails(tmp_path: Path) -> None:
    got = F.judge(report=_report(tmp_path, backlog_overdue=41), ledger=_ledger(tmp_path))
    assert got["verdict"] == "FAIL"
    assert any("backlog_overdue rose" in r for r in got["reasons"])


def test_a_rise_of_one_is_a_rise(tmp_path: Path) -> None:
    """A ratchet is not a band. Tolerating "small" regressions is how a floor becomes a
    suggestion."""
    got = F.judge(report=_report(tmp_path, overdue_wait_h=100.001), ledger=_ledger(tmp_path))
    assert got["verdict"] == "FAIL"


def test_the_raw_oldest_wait_is_published_and_fails_nothing(tmp_path: Path) -> None:
    """THE RED GATE THIS RULE WAS LEARNED FROM. The first version ratcheted `oldest_wait_h` and
    failed on the third live pass -- 6.0h to 6.3h -- because eighteen minutes had passed. No
    drain can make a clock run backwards inside a pass, so that gate was unsatisfiable, and an
    unsatisfiable gate gets switched off. A wait under the lease is the queue working."""
    got = F.judge(report=_report(tmp_path, oldest_wait_h=9_999.0), ledger=_ledger(tmp_path))
    assert got["verdict"] == "PASS", got["reasons"]
    row = next(r for r in got["checks"] if r["metric"] == "oldest_wait_h")
    assert row["state"] == "REPORTED"
    assert "fenced by nothing" in row["direction"]


def test_a_falling_cumulative_drain_fails(tmp_path: Path) -> None:
    """A cumulative count cannot fall. If it did, the ledger was reset or the organ lost its
    history, and either way the other ratchets are reading against nothing."""
    got = F.judge(report=_report(tmp_path, drained_total=3.0), ledger=_ledger(tmp_path))
    assert got["verdict"] == "FAIL"
    assert any("drained_total fell" in r for r in got["reasons"])


def test_a_rising_uncrawled_count_with_no_seeding_fails(tmp_path: Path) -> None:
    """The backlog grew and the desk learned nothing. That is the genuine regression."""
    got = F.judge(report=_report(tmp_path, uncrawled_total=900, seeded_this_pass=0),
                  ledger=_ledger(tmp_path))
    assert got["verdict"] == "FAIL"
    assert any("registered\nNO new ground" in r.replace(" NO new ground", "\nNO new ground")
               or "NO new ground" in r for r in got["reasons"])


# --------------------------------------------------------- the exception that is not a loophole
def test_a_rise_after_seeding_passes_and_the_report_says_why(tmp_path: Path) -> None:
    """THE TEST A LATER REVIEWER WILL WANT TO DELETE. Seeding lawful ground the registry had
    never heard of raises the uncrawled count BY DESIGN -- the count was low from ignorance, not
    from coverage. Measured on the first live pass: 148 -> 1259 while the OVERDUE backlog fell
    123 -> 63. Failing here would make the organ's own first duty a gate breach."""
    got = F.judge(report=_report(tmp_path, uncrawled_total=1259, seeded_this_pass=1284),
                  ledger=_ledger(tmp_path))
    assert got["verdict"] == "PASS", got["reasons"]
    row = next(r for r in got["checks"] if r["metric"] == "uncrawled_total")
    assert row["state"] == "SEEDED"
    assert "1284 newly known lawful ground" in row["why"]
    assert "the overdue ratchet above is what holds it to account" in row["why"]


def test_seeding_does_not_excuse_a_rising_overdue_backlog(tmp_path: Path) -> None:
    """The exception is scoped to ONE metric. A newly seeded root is not overdue, so nothing
    about seeding can explain the overdue count going up."""
    got = F.judge(report=_report(tmp_path, backlog_overdue=99, uncrawled_total=1259,
                                 seeded_this_pass=1284),
                  ledger=_ledger(tmp_path))
    assert got["verdict"] == "FAIL"
    assert any("backlog_overdue rose" in r for r in got["reasons"])


# -------------------------------------------------------------------------------- first reading
def test_a_first_reading_enters_at_what_was_measured(tmp_path: Path) -> None:
    """Never at an invented zero. CLAUDE.md records what inventing an unmeasured floor cost the
    desk the last time (a memory floor sized off a different machine)."""
    got = F.judge(report=_report(tmp_path), ledger=tmp_path / "absent.json")
    assert got["verdict"] == "PASS"
    rows = {r["metric"]: r for r in got["checks"]}
    assert rows["backlog_overdue"]["state"] == "FIRST"
    assert "never an invented zero" in rows["backlog_overdue"]["why"]
    assert rows["drained_total"]["state"] == "FIRST"


# ---------------------------------------------------------------------------------- UNMEASURED
def test_an_absent_report_is_unmeasured_and_exits_zero(tmp_path: Path) -> None:
    """On a clean checkout "this machine has no desk state" is not "a law was broken". A fence
    that cries wolf on every PR gets disabled, which is how enforcement dies."""
    got = F.judge(report=tmp_path / "nope.json", ledger=tmp_path / "l.json")
    assert got["verdict"] == "UNMEASURED"
    assert got["reasons"] == []
    assert "UNMEASURED is a real answer and it is not a pass" in got["why"]


def test_an_absent_report_on_the_box_is_a_failure(tmp_path: Path) -> None:
    """Where the state is real, an organ that was scheduled and produced nothing is L1.49."""
    got = F.judge(report=tmp_path / "nope.json", ledger=tmp_path / "l.json",
                  require_state=True)
    assert got["verdict"] == "FAIL"
    assert got["reasons"]


def test_an_unmeasured_pass_is_not_a_pass(tmp_path: Path) -> None:
    """The organ ran, could not read the registry, and said so. That is a verdict."""
    path = tmp_path / "COVERAGE_DRAIN.json"
    path.write_text(json.dumps({"at": _iso(), "status": "UNMEASURED",
                                "verdict": {"gap": "UNMEASURED", "what": "no registry"}}),
                    encoding="utf-8")
    assert F.judge(report=path, ledger=tmp_path / "l.json")["verdict"] == "UNMEASURED"
    assert F.judge(report=path, ledger=tmp_path / "l.json",
                   require_state=True)["verdict"] == "FAIL"


def test_a_report_with_no_measured_block_is_unmeasured(tmp_path: Path) -> None:
    path = tmp_path / "COVERAGE_DRAIN.json"
    path.write_text(json.dumps({"at": _iso(), "status": "MEASURED"}), encoding="utf-8")
    assert F.judge(report=path, ledger=tmp_path / "l.json")["verdict"] == "UNMEASURED"


# ----------------------------------------------------------------------------------- staleness
def test_a_stale_report_is_a_schedule_defect_and_not_a_backlog_rise(tmp_path: Path) -> None:
    """A stale number is not a worse number. Counting it as one would put the drain in breach
    every time a clock was disabled for an unrelated reason."""
    got = F.judge(report=_report(tmp_path, at=_iso(48.0)), ledger=_ledger(tmp_path))
    assert got["verdict"] == "PASS"
    row = next(r for r in got["checks"] if r["metric"] == "freshness")
    assert row["state"] == "STALE"
    assert "SCHEDULE defect" in row["why"]


def test_a_stale_report_on_the_box_is_a_failure(tmp_path: Path) -> None:
    got = F.judge(report=_report(tmp_path, at=_iso(48.0)), ledger=_ledger(tmp_path),
                  require_state=True)
    assert got["verdict"] == "FAIL"
    assert any("not running\non its clock" in r.replace(" on its clock", "\non its clock")
               or "not running" in r for r in got["reasons"])


# ------------------------------------------------------------------------------------ the CLI
def test_the_cli_exits_one_on_a_breach_and_writes_its_audit(tmp_path: Path) -> None:
    rpt = _report(tmp_path, backlog_overdue=999)
    led = _ledger(tmp_path)
    audit = tmp_path / "audit.json"
    rc = F.main(["--report", str(rpt), "--ledger", str(led), "--audit", str(audit)])
    assert rc == 1
    doc = json.loads(audit.read_text(encoding="utf-8"))
    assert doc["verdict"] == "FAIL"


def test_the_cli_exits_zero_when_unmeasured(tmp_path: Path) -> None:
    rc = F.main(["--report", str(tmp_path / "nope.json"), "--ledger", str(tmp_path / "l.json"),
                 "--audit", str(tmp_path / "a.json")])
    assert rc == 0


def test_the_render_names_the_days_largest_gap(tmp_path: Path) -> None:
    """Item 4 of the mandate: the bottleneck is a line somebody reads every morning."""
    lines = F.render(F.judge(report=_report(tmp_path), ledger=_ledger(tmp_path)))
    text = "\n".join(lines)
    assert "LARGEST GAP OVERDUE_UNCRAWLED_SOURCES" in text
    assert "fix:" in text


# ------------------------------------------------------------------------------- the wiring
def test_the_fence_runs_in_the_law_gate() -> None:
    """III.16: an organ is done only when something actually runs it. A fence nobody calls is a
    claim the desk cannot cash (L1.49)."""
    text = (_ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '"check_coverage_drain.py"' in text


def test_the_fence_caps_no_compute() -> None:
    """GROWTH GOVERNANCE Rule 1. This fence reads a report and compares two numbers; it must
    never be able to subtract a crawl, a worker or a second from any forest."""
    doc = F.__doc__ or ""
    assert "THIS FENCE CAPS NOTHING" in doc
    src = (_ROOT / "scripts" / "check_coverage_drain.py").read_text(encoding="utf-8")
    for forbidden in ("budget", "max_sources", "subprocess", "sleep("):
        assert forbidden not in src.replace("--budget-s", ""), forbidden


@pytest.mark.parametrize("metric", [*F.CEILINGS, *F.FLOORS])
def test_every_ratcheted_metric_is_judged(tmp_path: Path, metric: str) -> None:
    got = F.judge(report=_report(tmp_path), ledger=_ledger(tmp_path))
    assert metric in {r["metric"] for r in got["checks"]}
