"""A CLOCK THAT RUNS AND LANDS NOTHING IS THE STATE NO EXISTING CHECK COULD SEE.

`check_adoption_task` catches a scheduler entry that stopped. `check_adoption_lag` catches a
HEAD that is behind the tip. Between them sits the state the trading box was actually in for
four days, measured 2026-09-23:

    MT5-AdoptRelease   Status: Ready   Last Result: 1   Next Run: (an hour from now)
    adopt_and_seal.log: Adopt-Release exited 1 -- partial adoption   (x 40, one an hour)

The task ran. The mutex was taken. `Adopt-Release` completed. And the tree still differed from
the branch on a handful of CODE paths, so nothing sealed and the gateway kept running unshipped
code. adoption_lag would have caught the lag -- if anyone had been reading it; what nobody had,
and what made every hour a re-discovery, was WHICH PATHS and HOW LONG.

`check_adoption_partial` is that observation: the paths by name out of
`desks/mt5/reports/ADOPTION_STATE.json`, and the length of the unbroken run of partial passes
out of the adoption log the box already writes.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from desks.mt5.research import plumbing_watchdog as pw  # noqa: E402

NOW = datetime(2026, 9, 23, 6, 0, tzinfo=UTC)


def _box(tmp_path: Path, *, state: dict[str, Any] | None = None,
         log: str | None = None) -> Path:
    (tmp_path / "desks" / "mt5" / "reports").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "logs").mkdir(parents=True)
    if state is not None:
        (tmp_path / "desks" / "mt5" / "reports" / "ADOPTION_STATE.json").write_text(
            json.dumps(state), encoding="utf-8")
    if log is not None:
        (tmp_path / "desks" / "mt5" / "logs" / "adopt_and_seal.log").write_text(
            log, encoding="utf-8")
    return tmp_path


_PARTIAL_LINE = ("{t} adopt-and-seal: Adopt-Release exited 1 -- partial adoption; NOT sealing "
                 "a tree that only half-matches the branch")


# ------------------------------------------------------------------ the length of the outage
def test_the_consecutive_partial_run_is_counted_not_guessed(tmp_path: Path) -> None:
    log = "\n".join([
        "2026-09-22 20:00:00Z adopt-and-seal: sealed abc123456789 from main; resident asked",
        _PARTIAL_LINE.format(t="2026-09-23 03:00:00Z"),
        _PARTIAL_LINE.format(t="2026-09-23 04:00:00Z"),
        _PARTIAL_LINE.format(t="2026-09-23 05:00:00Z"),
    ]) + "\n"
    box = _box(tmp_path, log=log)
    facts = pw.adoption_partial_run(box / "desks/mt5/logs/adopt_and_seal.log", NOW)
    assert facts["consecutive"] == 3
    assert facts["since"] == "2026-09-23 03:00:00Z"
    assert facts["hours"] == 3.0


def test_a_seal_ends_the_run_so_one_bad_hour_is_not_an_outage(tmp_path: Path) -> None:
    log = "\n".join([
        _PARTIAL_LINE.format(t="2026-09-23 01:00:00Z"),
        "2026-09-23 02:00:00Z adopt-and-seal: sealed deadbeef1234 from main",
        _PARTIAL_LINE.format(t="2026-09-23 05:00:00Z"),
    ]) + "\n"
    box = _box(tmp_path, log=log)
    assert pw.adoption_partial_run(box / "desks/mt5/logs/adopt_and_seal.log", NOW)[
        "consecutive"] == 1


def test_an_absent_log_is_unmeasured_and_never_zero(tmp_path: Path) -> None:
    """"The adoption is healthy" and "nobody wrote the log" must not render the same (L1.28a)."""
    facts = pw.adoption_partial_run(tmp_path / "nope.log", NOW)
    assert facts["consecutive"] == pw.UNMEASURED
    assert facts["hours"] == pw.UNMEASURED


def test_the_named_paths_do_not_end_the_run_they_belong_to(tmp_path: Path) -> None:
    """Adopt-And-Seal now writes the offending paths into the same log, indented under the
    status line. A counter that treated one of those as an outcome would report 1 where the
    truth is 3."""
    log = "\n".join([
        "2026-09-22 20:00:00Z adopt-and-seal: sealed abc123456789 from main",
        _PARTIAL_LINE.format(t="2026-09-23 03:00:00Z"),
        "2026-09-23 03:00:01Z adopt-and-seal:     desks/mt5/research/engine.py",
        _PARTIAL_LINE.format(t="2026-09-23 04:00:00Z"),
        _PARTIAL_LINE.format(t="2026-09-23 05:00:00Z"),
    ]) + "\n"
    box = _box(tmp_path, log=log)
    got = pw.adoption_partial_run(box / "desks/mt5/logs/adopt_and_seal.log", NOW)
    # The path line carries Log()'s timestamp prefix, so it is not indented at column 0: the
    # indentation is in the MESSAGE BODY, and that is what has to be recognised. Read as an
    # outcome it would end the very run it is evidence for -- three hours reported as two.
    assert got["consecutive"] == 3
    assert got["since"] == "2026-09-23 03:00:00Z"


# --------------------------------------------------------------------------- the defect itself
def test_a_partial_adoption_is_a_critical_defect_that_names_the_paths(tmp_path: Path) -> None:
    box = _box(
        tmp_path,
        state={"measured_at": "2026-09-23T05:00:00Z", "ok": False,
               "code_drift": ["desks/mt5/research/engine.py", "libs/ops/release.py"],
               "unwritable": ["desks/mt5/research/engine.py"],
               "counts": {"code_drift": 2}},
        log=_PARTIAL_LINE.format(t="2026-09-23 05:00:00Z") + "\n")
    rows, facts = pw.check_adoption_partial(box, NOW)
    assert len(rows) == 1
    row = rows[0]
    assert row["check"] == "adoption_partial"
    assert row["severity"] == "CRITICAL"
    assert "desks/mt5/research/engine.py" in row["evidence"]
    assert "libs/ops/release.py" in row["evidence"]
    assert "1 consecutive hourly pass(es)" in row["evidence"]
    assert "ADOPTION_STATE.json" in row["repair"]
    assert facts["code_drift"] == 2
    assert facts["state"] == "partial"


def test_a_clean_adoption_raises_nothing_and_still_publishes_the_facts(tmp_path: Path) -> None:
    box = _box(tmp_path, state={"measured_at": "2026-09-23T05:00:00Z", "ok": True,
                                "code_drift": [], "unwritable": [], "counts": {}},
               log="2026-09-23 05:00:00Z adopt-and-seal: sealed abc123456789 from main\n")
    rows, facts = pw.check_adoption_partial(box, NOW)
    assert rows == []
    assert facts["state"] == "ok"
    assert facts["code_drift"] == 0


def test_an_absent_artifact_is_unmeasured_and_invents_no_defect(tmp_path: Path) -> None:
    """A box that has not adopted since this shipped has no artifact, and adoption_lag already
    covers a tree that is behind. Inventing a defect from an absent file is the opposite of the
    discipline this organ exists for."""
    box = _box(tmp_path, log="")
    rows, facts = pw.check_adoption_partial(box, NOW)
    assert rows == []
    assert facts["state"] == pw.UNMEASURED


def test_an_unwritable_path_is_named_with_its_likely_cause(tmp_path: Path) -> None:
    box = _box(tmp_path,
               state={"ok": False, "code_drift": ["a.py"], "unwritable": ["a.py"],
                      "counts": {}},
               log=_PARTIAL_LINE.format(t="2026-09-23 05:00:00Z") + "\n")
    rows, _facts = pw.check_adoption_partial(box, NOW)
    assert "could not be written or unlinked" in rows[0]["evidence"]
    assert "chkdsk" in rows[0]["repair"]


# -------------------------------------------------------------- UNWIRED IS A DEFECT (III.16)
def test_the_check_is_on_the_watchdog_s_own_clock_and_has_an_escalation_window() -> None:
    assert "adoption_partial" in pw.ESCALATION_S
    src = Path(pw.__file__).read_text(encoding="utf-8")
    assert '("adoption_partial", lambda: check_adoption_partial(base, t))' in src, \
        "the check exists but run() never calls it"


def test_the_artifact_path_is_the_one_the_adopt_script_writes() -> None:
    """Two organs with different ideas of where the artifact lives is a watchdog that watches
    nothing."""
    adopt = (DESK / "scripts" / "Adopt-Release.ps1").read_text(encoding="utf-8")
    assert '"ADOPTION_STATE.json"' in adopt
    assert 'Join-Path $RepoRoot "desks\\mt5\\reports"' in adopt
    assert pw.ADOPTION_STATE.name == "ADOPTION_STATE.json"
    assert pw.ADOPTION_STATE.parent.name == "reports"
