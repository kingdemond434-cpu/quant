"""The chain ran in the wrong order for a day and every organ reported success.

MEASURED 2026-08-12, after the order was moved out of cron minutes and into one list:

  * `finalize_axis_screens` fired at 07:08 and the vol-risk-premium screen at 10:37, so that
    screen's raw verdicts were not CORRECTED until 07:08 the next day. The spawner admits only on
    `verdict_adjusted`, so the extra 11:05 spawner pass added to cut latency was reading
    corrections computed BEFORE the screen it was meant to catch. It bought nothing for that axis.
  * `run_slot_retirement` fired at 11:45, forty minutes AFTER the last spawner pass. A slot freed
    by a retirement sat empty until 08:45 the next morning -- 21 hours of the desk's scarcest
    resource, idle, with 26 survivors queued for it.

Neither appeared in a log. Every organ ran, every organ exited 0. That is why the order is a data
structure now and why these tests read it: an ordering defect is invisible by construction, so the
only thing that can catch it is something that looks at the order itself.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def cyc():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_pipeline_cycle", _REPO / "scripts/run_pipeline_cycle.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _order(cyc) -> list[str]:
    return [s[0] for s in cyc.STAGES]


# ------------------------------------------------------------------ the two inverted orderings
def test_verdicts_are_corrected_before_anything_reads_them(cyc) -> None:
    """THE FIRST INVERSION. The spawner admits only on `verdict_adjusted`. With finalize running
    after the screen's consumers, a fresh screen's survivors were invisible for a full day."""
    o = _order(cyc)
    assert o.index("finalize_axis_screens.py") < o.index("run_paper_sleeve_spawner.py")
    assert o.index("finalize_axis_screens.py") == 0, "nothing may read a raw verdict"


def test_slots_are_freed_before_they_are_filled(cyc) -> None:
    """THE SECOND INVERSION, and the expensive one. Retiring after the spawner means a freed slot
    waits a whole cycle for a queue that is 26 deep."""
    o = _order(cyc)
    assert o.index("run_slot_retirement.py") < o.index("run_paper_sleeve_spawner.py")


def test_a_clock_is_judged_on_this_cycles_evidence_not_the_last_one(cyc) -> None:
    """Observation and the liveness verdict both precede retirement, so nothing is retired on a
    stale reading of whether it was accruing."""
    o = _order(cyc)
    assert o.index("run_paper_sleeve_forward.py") < o.index("run_slot_retirement.py")
    assert o.index("check_slot_liveness.py") < o.index("run_slot_retirement.py")


def test_capital_authority_follows_the_spawn_and_the_dashboard_follows_both(cyc) -> None:
    o = _order(cyc)
    assert o.index("run_paper_sleeve_spawner.py") < o.index("run_promotion_actuator.py")
    assert o[-1] == "publish_pipeline.py", "the dashboard must render the state after it settles"


def test_every_stage_says_why_it_sits_where_it_does(cyc) -> None:
    """An order with no stated reasons is an order nobody can safely edit."""
    for script, _args, why in cyc.STAGES:
        assert why and len(why) > 20, script


# ------------------------------------------------------------------ speed must not erode safety
def test_the_promotion_hold_is_wall_clock_not_a_run_count() -> None:
    """THE TRAP THIS NEARLY WALKED INTO. The actuator's hold was CONFIRM_RUNS=2, correct only
    because it ran daily. At a 15-minute cycle the same constant means THIRTY MINUTES of required
    agreement instead of two days -- a safety property silently gutted by a cadence change, with
    no edit to the safety logic and nothing to notice.

    In hours, cadence and safety are independent: the desk can react faster to everything EXCEPT
    the one transition where haste is the hazard.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_promotion_actuator", _REPO / "scripts/run_promotion_actuator.py")
    act = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(act)

    assert not hasattr(act, "CONFIRM_RUNS"), (
        "a run-counted hold shrinks every time the cycle speeds up")
    assert act.CONFIRM_HOLD_H >= 24.0
    src = (_REPO / "scripts/run_promotion_actuator.py").read_text("utf-8")
    assert "held_h" in src and "gate_rung_since" in src


def test_the_append_only_stage_is_rate_limited_and_says_so(cyc, tmp_path: Path) -> None:
    """The forward observer APPENDS a row per run. At 15 minutes that is 96 rows per sleeve per
    day about sources that regenerate at most daily -- a ledger of the observer's cadence, not of
    the desk's evidence. And the skip must be REPORTED: a silent skip is indistinguishable from a
    stage that ran and found nothing, which is the exact ambiguity this pipeline keeps paying for.
    """
    assert cyc._APPEND_ONLY == "run_paper_sleeve_forward.py"
    assert cyc.FORWARD_MIN_GAP_H >= 1.0

    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / cyc._FORWARD_LEDGER).write_text("{}\n", "utf-8")
    d = cyc.run(root=tmp_path, dry_run=True)
    row = next(r for r in d["stages"] if r["stage"] == cyc._APPEND_ONLY)
    assert row["status"] == "SKIPPED-RATE-LIMIT"
    assert "Not a failure" in row["why"]


def test_a_rate_limit_skip_is_not_counted_as_a_failure(cyc, tmp_path: Path) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / cyc._FORWARD_LEDGER).write_text("{}\n", "utf-8")
    assert cyc.run(root=tmp_path, dry_run=True)["n_failed"] == 0


def test_an_absent_ledger_does_not_skip_the_observer(cyc, tmp_path: Path) -> None:
    """UNKNOWN AGE MUST NOT SUPPRESS THE STAGE. A missing ledger means it has never run here, and
    resolving that toward 'skip' would keep a fresh box permanently unobserved."""
    d = cyc.run(root=tmp_path, dry_run=True)
    row = next(r for r in d["stages"] if r["stage"] == cyc._APPEND_ONLY)
    assert row["status"] == "DRY-RUN"


# ------------------------------------------------------------------ failure isolation
def test_one_broken_stage_never_stops_the_rest(cyc) -> None:
    """Each stage is independently useful and idempotent. Aborting the chain because one screen
    was mid-write would turn a transient into an outage."""
    src = (_REPO / "scripts/run_pipeline_cycle.py").read_text("utf-8")
    body = src.split('"""', 2)[2]
    assert "break" not in body, "a failing stage must not short-circuit the cycle"
    assert "raise" not in body.split("if __name__")[0], "no stage failure may propagate"


def test_a_failed_stage_is_still_reported_and_fails_the_run(cyc) -> None:
    """Isolation is not silence. A persistently broken stage has to be visible."""
    src = (_REPO / "scripts/run_pipeline_cycle.py").read_text("utf-8")
    assert 'return 1 if doc["n_failed"] else 0' in src


def test_every_stage_has_a_hang_guard(cyc) -> None:
    """A hung stage on a 15-minute cycle is a stuck flock and a dead pipeline."""
    assert cyc.STAGE_TIMEOUT_S <= 600
    src = (_REPO / "scripts/run_pipeline_cycle.py").read_text("utf-8")
    assert "timeout=STAGE_TIMEOUT_S" in src and "TimeoutExpired" in src


# ------------------------------------------------------------------ the live wiring
def test_the_cycle_is_scheduled_and_the_old_lines_are_gone() -> None:
    """Two schedules for one organ under different locks is a race a flock cannot serialise --
    R0048. Consolidating means the individual lines must actually be REMOVED, not left behind."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    lines = [ln for ln in man.splitlines() if ln[:1] in "0123456789*"]
    assert any("run_pipeline_cycle.py" in ln for ln in lines), "the cycle is on no schedule"
    for stage in ("finalize_axis_screens.py", "run_paper_sleeve_forward.py",
                  "check_slot_liveness.py", "run_slot_retirement.py",
                  "run_paper_sleeve_spawner.py", "run_promotion_actuator.py",
                  "publish_pipeline.py"):
        assert not any(stage in ln for ln in lines), (
            f"{stage} still has its own cron line AND runs inside the cycle -- two launchers, "
            "one artifact, split locks")


def test_the_cycle_runs_often_enough_to_mean_immediately() -> None:
    """The whole chain is 6.5s of local CPU. 'As fast as possible' is bounded by what the sources
    do, not by what the pipeline costs."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    line = next(ln for ln in man.splitlines()
                if ln[:1] in "0123456789*" and "run_pipeline_cycle.py" in ln)
    minute = line.split()[0]
    assert minute.startswith("*/"), f"cycle minute field is {minute!r}, not a sub-hourly interval"
    assert int(minute[2:]) <= 15, "a survivor should reach shadow in minutes, not hours"


def test_the_cycle_holds_one_lock() -> None:
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    line = next(ln for ln in man.splitlines()
                if ln[:1] in "0123456789*" and "run_pipeline_cycle.py" in ln)
    assert "flock -n " in line, "a slow cycle must make the next a no-op, never a double-run"


def test_it_runs_clean_on_this_box(cyc) -> None:
    d = cyc.run(root=_REPO, dry_run=True)
    assert d["n_stages"] == len(cyc.STAGES)
    assert "DEPENDENCY GRAPH" in d["order_law"]
    p = _REPO / cyc.OUT
    if p.exists():
        assert json.loads(p.read_text("utf-8"))["n_failed"] == 0
