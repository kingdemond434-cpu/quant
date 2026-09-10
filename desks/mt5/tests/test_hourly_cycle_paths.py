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

    Matches an INDENTED import statement, not the bare phrase -- the phrase also appears in the
    comment explaining the bug, and a test that matches prose instead of code proves nothing about
    code. The indent is not pinned to one depth: these imports have already moved between a
    function body and a nested helper once, and re-pinning the column each time tests the layout
    rather than the ordering this file exists to protect.
    """
    first_use = min(SRC.index(f"\n{' ' * n}from mt5desk import")
                    for n in (4, 8) if f"\n{' ' * n}from mt5desk import" in SRC)
    assert SRC.index("sys.path.insert(0, _p)") < first_use


def test_the_repo_root_is_on_the_path_too() -> None:
    """`_costed` imports `libs.ops.compute_ledger` from the REPOSITORY root, which was never added.

    MEASURED on the box 2026-09-06: `ModuleNotFoundError: No module named 'libs.ops'` on the first
    costed leg of every run. `_costed` catches it and runs the leg regardless -- by design, a
    ledger must not take down the work it measures -- so the cycle recorded no compute at all,
    hour after hour, while `libs.ops.allocators` reported COMPUTE as the weakest link in the stack
    for want of exactly the denominator these runs were meant to produce. Nothing failed and
    nothing was measured, which is the hardest shape of defect to see.
    """
    setup = SRC.split("def ", 1)[0]
    assert "REPO = " in setup, "the repository root is not derived at module level"
    assert "str(REPO)" in setup.split("for _p in")[1].split("\n")[0], \
        "REPO is derived but never placed on sys.path"


def test_the_tape_failure_is_still_reported_not_swallowed() -> None:
    """It failed loudly for five days and nothing escalated it -- keep the line, and keep it
    findable, because the next import break will look exactly the same."""
    assert 'print(f"tick tape ' in SRC and "FAILED:" in SRC


def test_the_two_recorders_do_not_share_a_verdict() -> None:
    """MEASURED 2026-09-06: `tape.main` recorded 359,107 broker-native ticks and `triangle_tape`
    then raised, so the shared `try` returned one error and the hour read as "tick tape FAILED" --
    for a leg whose irreplaceable half had just succeeded. Ticks cannot be backfilled; triangles
    recompute from them in seconds. They must fail independently."""
    body = SRC.split("def record_tape", 1)[1].split("\ndef ", 1)[0]
    assert "tape_exit_code" not in body or "results[f\"{label}_exit_code\"]" in body
    assert "_tape_main" in body and "_triangle_main" in body, \
        "the two recorders are not invoked through separately-guarded calls"


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


def test_one_leg_failure_cannot_terminate_later_independent_legs(tmp_path, monkeypatch) -> None:
    """Written on the VPS (2026-09-06) against its own `_costed`, which read a leg's SystemExit
    as that leg's verdict; the desk's `_costed` (2026-09-07) re-raises SystemExit because every
    in-process leg that can raise it already reports its own code at the call. The two were
    merged 2026-09-08 on the desk's rule, so this pins the BEHAVIOUR both were written for --
    a failing leg is recorded and the legs after it still run -- rather than either file's text.
    """
    import hourly_cycle

    # THIS TEST WAS WRITING SIMULATED FAILURES INTO THE DESK'S REAL EVENT LOG. `_costed` calls
    # `_emit_leg` -> `libs.ops.events.leg_events`, which appends to the tracked, committed
    # `desks/mt5/data/events.jsonl` -- so every run of this file left rows reading
    # `{"leg": "bad", "outcome": "RuntimeError: simulated: one broken organ"}` in the log that
    # consumers read to ask what happened since they last looked. Found 2026-09-10 as an
    # untracked file after a suite run; a fabricated LEG_FAILED is the one thing an event log
    # must never contain, and the same class as R0748 (a test writing to a tracked path).
    emitted: list[tuple[str, str]] = []
    monkeypatch.setattr(hourly_cycle, "_emit_leg",
                        lambda name, outcome: emitted.append((name, outcome)))
    # AND THE COMPUTE LEDGER, WHICH IS THE SECOND LEAK FROM THE SAME CALL. `_costed` also opens
    # and closes a `compute_ledger` run, so this test was appending
    #   {"run": "bad", "outcome": "RuntimeError: simulated: one broken organ"}
    # to `data/compute_ledger.jsonl` -- the desk's compute DENOMINATOR, which `cost_by_run`
    # aggregates and `libs.ops.completion._streak` reads to tell a blip from an outage. A leg
    # named "bad" that never existed, failing forever, is exactly the kind of row that makes a
    # scaling law unreadable. `_costed` imports the ledger locally, so the module's own LEDGER
    # path is the thing to redirect; when `libs` is not importable at all (the desk-root
    # invocation) nothing is written and there is nothing to redirect, which is why this is
    # tolerant rather than required.
    try:
        from libs.ops import compute_ledger as _cl
        monkeypatch.setattr(_cl, "LEDGER", tmp_path / "compute_ledger.jsonl")
    except Exception:                                                   # noqa: BLE001
        pass

    ran: list[str] = []

    def bad() -> dict:
        raise RuntimeError("simulated: one broken organ")

    def later() -> dict:
        ran.append("later")
        return {"ok": True}

    first = hourly_cycle._costed("bad", bad)
    second = hourly_cycle._costed("later", later)
    assert first["status"] == "LEG_FAILED" and "RuntimeError" in first["error"]
    assert second == {"ok": True} and ran == ["later"], (
        "a leg's failure must be a recorded verdict, never authority to stop the pass")
    assert emitted == [("bad", "RuntimeError: simulated: one broken organ"), ("later", "ok")], (
        "both legs must reach the event log, the failure with its reason attached")
    body = SRC.split("def _costed(", 1)[1].split("\ndef ", 1)[0]
    assert "except BaseException as exc:" in body
    assert "close_run(run, outcome=" in body, "the failure must reach the compute ledger"


def test_a_leg_that_fails_without_raising_is_not_recorded_as_ok():
    """THE DEFECT THIS DESK PAID MOST FOR, found independently on the VPS branch and merged here.

    `_producer` returns a DICT. A non-zero exit, a MISSING script and a timeout all come back as
    DATA -- nothing is raised -- so the `except` arm above never runs and the ledger wrote `ok`.
    `pf_allocator` exited 1 every hour for six days and every compute-ledger row for it said ok,
    which is why the streak that separates a blip from an outage counted zero the whole time.
    `libs.ops.completion._streak` reads exactly this field.
    """
    body = SRC.split("def _costed(", 1)[1].split("\ndef ", 1)[0]
    assert 'outcome = "ok"' in body, "the outcome is no longer derived from the leg's return"
    for shape in ('out.get("error")', '"exit_code"', 'out.get("timeout_s")', 'status'):
        assert shape in body, (
            f"_costed no longer inspects {shape!r}, so a leg that fails by RETURNING a failure "
            f"is recorded as a success again")
    assert 'close_run(run, outcome=outcome)' in body


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
