"""The hourly cycle must be able to import the desk's own packages BEFORE it uses them.

MEASURED 2026-08-27 on the desk box: 66 consecutive `tick tape FAILED: ModuleNotFoundError: No
module named 'mt5desk'` lines since the log was created on 08-22 -- five days of broker-native
ticks never recorded. `record_tape()` runs BEFORE `daily()`, and `daily_cycle` was the module
that happened to insert BASE into sys.path, so the tape import always arrived too early. A tick
nobody recorded is GONE: unlike a bar, it cannot be re-downloaded.
"""
from __future__ import annotations

from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
SRC = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")


def test_base_is_on_sys_path_before_any_function_runs() -> None:
    setup = SRC.split("def ", 1)[0]
    assert "sys.path.insert(0, _p)" in setup, "BASE is not put on sys.path at module level"
    assert "import sys" in setup


def test_the_tape_import_is_not_reached_before_the_path_is_set() -> None:
    """Order is the whole defect: the fix is worthless if the insert lands after first use.

    Matches the INDENTED statement, not the bare phrase -- the phrase also appears in the comment
    explaining the bug, and a test that matches prose instead of code proves nothing about code.
    """
    assert SRC.index("sys.path.insert(0, _p)") < SRC.index("\n        from mt5desk import")


def test_the_tape_failure_is_still_reported_not_swallowed() -> None:
    """It failed loudly for five days and nothing escalated it -- keep the line, and keep it
    findable, because the next import break will look exactly the same."""
    assert 'print(f"tick tape FAILED:' in SRC


def test_state_vector_cannot_terminate_the_hourly_controller() -> None:
    """Native model failure is contained in a subprocess, not the factory process."""
    body = SRC.split("def state_vector()", 1)[1].split("\ndef ", 1)[0]
    assert "subprocess.run(" in body
    assert '"state_vector_build.py"' in body
    assert "STATE_VECTOR_HOURLY_BUDGET_SEC" in body
    assert "state_vector_build.main()" not in body
    assert '"status": "OK" if r.returncode == 0 else "FAILED"' in body


def test_daily_promotion_chain_cannot_terminate_hourly_discovery() -> None:
    body = SRC.split("def daily()", 1)[1].split("\ndef ", 1)[0]
    assert "subprocess.run(" in body
    assert '"daily_cycle.py"' in body
    assert "DAILY_CYCLE_HOURLY_BUDGET_SEC" in body
    assert "daily_cycle.main(" not in body


def test_one_leg_failure_cannot_terminate_later_independent_legs() -> None:
    body = SRC.split("def _costed(", 1)[1].split("\ndef ", 1)[0]
    assert "except KeyboardInterrupt:" in body
    assert "except BaseException as exc:" in body
    assert '"status": "FAILED"' in body
    assert "except BaseException as exc:\n        close_run" in body
    assert "close_run(run, outcome=f" in body


# ------------------------------------------------------- the loop that has to never stop, 24/7

LAUNCHER = (DESK / "scripts" / "MT5Hourly.cmd").read_text("utf-8")
#: The launcher's CODE, with `rem` commentary stripped. The same trap this file already documents
#: for `hourly_cycle.py`: the comment explaining a defect necessarily contains the defect's text,
#: so a fence matching the raw file proves nothing about what the box actually executes.
LAUNCHER_CODE = "\n".join(ln for ln in LAUNCHER.splitlines()
                          if not ln.strip().lower().startswith("rem"))


def test_the_launcher_loops_forever() -> None:
    """`MT5Hourly.cmd` is the ONLY launcher of the cycle, so a launcher that exits after one pass
    stops the desk's entire discovery chain until somebody notices."""
    assert ":loop" in LAUNCHER_CODE and "goto loop" in LAUNCHER_CODE
    assert "research\\hourly_cycle.py" in LAUNCHER_CODE


def test_the_period_is_measured_from_the_hour_not_from_the_end_of_the_pass() -> None:
    """THE DEFECT THE DEEPENING WORK EXPOSED. `timeout /t 3540` counts from the moment the cycle
    RETURNS, so the real period is (pass duration + 59 min). A pass that now drains the deepening
    queue for up to 40 minutes turns an "hourly" loop into one firing every hour and three
    quarters, sliding further every pass -- and nothing reports it, because the marker is written
    on every pass so the cycle looks healthy while its cadence halves.

    Sleeping to the top of the next hour makes the period what the name says whatever the pass
    costs. Asserted on the ARITHMETIC, so a future edit that reintroduces a fixed post-pass wait
    fails here rather than silently slowing the desk down."""
    assert "timeout /t 3540" not in LAUNCHER_CODE, "the period runs from the end of the pass"
    assert "3600.0 - (time.time() %% 3600.0)" in LAUNCHER_CODE
    assert "max(60.0," in LAUNCHER_CODE, "a zero-cost pass would spin without a floor"
