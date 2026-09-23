"""THE RESEARCH CYCLE -- the desk automated every generator and left execution manual.

MEASURED 2026-08-08: nine systemd timers, every one of them a MINER. Nothing scheduled the bar
build or a single study. So the stage the desk's own funnel diagnosis calls the bottleneck
(EXECUTION) was the only stage a human had to type, while the stages it says are NOT the constraint
ran daily and unattended.

That is L1.52(a)'s asymmetry inverted -- `queue backlogged -> EXECUTE` -- and it is why the desk
could hold 898,560 candidates against 0 executed trials for weeks without anything looking broken.
"""

from __future__ import annotations

import re
from pathlib import Path

CYCLE = Path("ops/run_research_cycle.sh")
SERVICE = Path("ops/quant-midnight-frontier.service")
TIMER = Path("ops/quant-midnight-frontier.timer")


def test_THE_MIDNIGHT_CONTROLLER_SNAPSHOTS_THE_MT5_FACTORY() -> None:
    """The legacy research cycle remains testable, but the midnight venue is MT5/Fusion only."""
    assert CYCLE.exists() and SERVICE.exists() and TIMER.exists()
    assert "run_midnight_frontier.sh" in SERVICE.read_text("utf-8")
    midnight = Path("ops/run_midnight_frontier.sh").read_text("utf-8")
    assert "build_mt5_midnight_state.py" in midnight
    assert "run_sweep_then_cycle.sh" not in midnight
    assert "OnCalendar" in TIMER.read_text("utf-8")


def test_THE_ORDER_IS_BARS_THEN_STUDIES_THEN_LADDER() -> None:
    """Bars must exist before a study reads them, and the ladder must run AFTER the sweep so a
    fresh Stage-A survivor is owed its shadow start the same day it is found -- the forward clock
    is the one input that cannot be bought later."""
    src = CYCLE.read_text("utf-8")
    i_bars = src.index("build_bars.py")
    i_study = src.index("run_study_on_vps.sh")
    i_ladder = src.index("run_live_ladder.py")
    assert i_bars < i_study < i_ladder, "the cycle runs its stages out of dependency order"


def test_THE_ZERO_CAPITAL_CLOCK_EXISTS_BEFORE_THE_LADDER_READS_IT() -> None:
    """SHADOW produces untouched OOS evidence; the ladder cannot demand that evidence first."""
    for path in (CYCLE, CRON):
        src = path.read_text("utf-8")
        assert src.index("run_paper_sleeve_spawner.py") < src.index("run_live_ladder.py")
        assert src.index("run_paper_sleeve_forward.py") < src.index("run_live_ladder.py")


def test_THE_LADDER_RUNS_EVEN_ON_A_NULL_DAY() -> None:
    """It also reports what is ALREADY live, so a cycle that skipped it when the sweep found
    nothing would go silent exactly when a live record needs reading."""
    src = CYCLE.read_text("utf-8")
    assert "runs even when the sweep found nothing" in src


def test_IT_IS_NICED_BECAUSE_THE_RECORDERS_ARE_IRREPLACEABLE() -> None:
    """A study that starves the recorders costs tape that cannot be re-acquired at any price."""
    src = CYCLE.read_text("utf-8")
    assert "nice -n 15" in src
    assert "OMP_NUM_THREADS=1" in src


def test_THE_TIMER_STARTS_THE_OVERNIGHT_FRONTIER_AT_LOCAL_MIDNIGHT() -> None:
    """One existing timer starts the renewable cycle; the wrapper lock rejects duplicates."""
    timer = TIMER.read_text("utf-8")
    assert "00:00:00 Europe/Dublin" in timer
    assert ".overnight_frontier.lock" in Path("ops/run_sweep_then_cycle.sh").read_text("utf-8")
    assert ".midnight_controller_cycle.lock" in Path("ops/run_midnight_frontier.sh").read_text(
        "utf-8"
    )
    assert "Persistent=true" in TIMER.read_text("utf-8"), (
        "a missed cycle should run on the next boot rather than being skipped silently"
    )


def test_THE_BAR_BUDGET_IS_OVERRIDABLE_BUT_HAS_A_SANE_DEFAULT() -> None:
    """build_bars streams now, so memory is O(buckets) -- but the budget still costs wall time and
    competes with the recorders, so it is a declared default rather than an unbounded job."""
    src = CYCLE.read_text("utf-8")
    assert "BARS_FILE_BUDGET:-" in src


#: The two stages whose non-zero exit is a DESIGNED VERDICT rather than a fault. Both publish a
#: judgement -- "these capabilities are unwired", "the book is BLOCKED" -- and a cycle that went
#: red because the preflight correctly reported a latched rail would train everyone to ignore red.
_MAY_SUPPRESS = ("check_unwired_capability.py", "run_golive_preflight.py")


def test_THE_CYCLE_CAN_ACTUALLY_FAIL() -> None:
    """THE ONE THAT MATTERS HERE. Every stage once ended in `|| true` and the closing line
    reported `exit $?` -- the status of the last `|| true`, which is 0 by construction. A cycle
    where the sweep crashed, the ladder never ran and the promotion path died printed the same
    "exit 0" as a clean one, so yesterday's artifacts were certified as today's work every night
    (L1.49: a gate that never ran is a claim the desk cannot cash).

    This was fixed once and then lost to a `--theirs` merge resolution on the box. That is exactly
    why it is a test and not a comment.
    """
    src = CYCLE.read_text("utf-8")
    assert "CYCLE_RC=0" in src and "trap 'record_failure" in src, (
        "the cycle has no ERR trap -- a failing stage leaves no record and the run reports success")
    assert 'exit "$CYCLE_RC"' in src, (
        "the cycle does not exit on its own latched status; `exit $?` reports only the LAST "
        "stage, which says nothing about the twenty before it")
    assert "exit $? at" not in src, "the old always-zero exit line is back"


def test_ONLY_THE_STAGES_THAT_PUBLISH_A_VERDICT_MAY_SUPPRESS_FAILURE() -> None:
    """`|| true` is how the silence came back last time. Each surviving one must be a stage whose
    non-zero exit is a judgement, and a new one added anywhere else fails here rather than being
    discovered a month later by wondering why the cycle is always green."""
    suppressed = [ln.strip() for ln in CYCLE.read_text("utf-8").splitlines()
                  if ln.rstrip().endswith("|| true") and not ln.strip().startswith("#")]
    for ln in suppressed:
        assert any(k in ln for k in _MAY_SUPPRESS), (
            f"stage suppresses its own failure and is not one of the two that may: {ln!r}. A "
            "cycle that cannot go red is a cycle nobody can trust when it is green")


def test_THE_TRAP_KEEPS_THE_CONTINUATION_THAT_MASKING_BOUGHT() -> None:
    """Failing closed must not mean stopping. `set -e` here would abort the whole run on the first
    stage that exits non-zero, taking the recorders and every downstream monitor with it -- which
    is a worse outage than the silence it replaced."""
    opts = [ln for ln in CYCLE.read_text("utf-8").splitlines() if ln.startswith("set ")]
    assert opts, "the cycle sets no shell options at all"
    for ln in opts:
        assert "-e" not in ln.replace("-uo", "").replace("-u", ""), (
            f"{ln!r} aborts the cycle on the first failure; the ERR trap records and continues")


def test_A_SNAPSHOT_SCREEN_IS_NEVER_LEFT_UNSCHEDULED() -> None:
    """RETARGETED 2026-09-05. This fence required `screen_copytrading.py` to be scheduled in the
    cycle. That screen read an exchange copytrading leaderboard, it is deleted with the retired
    crypto-exchange desk, and after the retirement its name survived only inside the comment that
    retired it -- so the fence PASSED off a comment while the screen ran nowhere. That is the
    failure mode it existed to catch, wearing the fence's own clothes.

    THE RULE IT ENCODES IS KEPT because it is not about copy traders. III.15 needs CALENDAR
    SEPARATION and nothing else can manufacture it: a screen that refuses to publish until it
    holds two cohort snapshots days apart accumulates NOTHING if nothing repeats it, and then
    reports NO-DATA -- a statement about the cron table rather than about the world (III.16,
    L1.28a). So: every snapshot-cadence screen the cycle names must be a script that EXISTS, and
    must be named on a line that actually runs.
    """
    src = _active(CYCLE.read_text("utf-8"))
    for script in re.findall(r"scripts/(screen_[a-z0-9_]+\.py)", src):
        assert Path("scripts", script).exists(), (
            f"the cycle schedules scripts/{script}, which does not exist -- the panel will report "
            "NO-DATA forever and the reason will be the scheduler rather than the evidence")


#: The retired crypto-exchange order path. These scripts are deleted; naming them here is how the
#: fence below stays specific about what must never come back.
_RETIRED_ORDER_PATH = (
    "run_spot_executor.py", "run_margin_executor.py", "run_discretionary_live.py",
    "run_spot_momentum.py", "run_mechanism_sleeves.py", "run_cashcarry_executor.py",
)


def _active(text: str) -> str:
    """The lines that actually run: comments stripped, in a .sh or a .py alike.

    Without this the fences below would be satisfied by a retirement NOTE that merely mentions a
    script -- which is exactly what happened on 2026-09-05, when commenting the crypto executors
    out of the cycle left `"run_spot_executor.py" in src` passing off the comment that retired it.
    A fence a comment can satisfy is not a fence.
    """
    return "\n".join(ln for ln in text.split("\n") if not ln.strip().startswith("#"))


def test_NO_CRYPTO_EXCHANGE_ORDER_PATH_IS_SCHEDULED_ON_THIS_BOX() -> None:
    """REPLACES `test_THE_ORDER_PATH_IS_SCHEDULED` and `test_THE_SCHEDULED_EQUITY_IS_READ_NOT_TYPED`
    (2026-09-05), which required the opposite and were measuring retired ground.

    Those fences were right for the desk that existed when they were written: a book computed
    nightly and never placed holds yesterday's positions forever, so the order path had to be
    SCHEDULED. The 2026-08-18 universe mandate retired the venue they placed on, and every one of
    those scripts is now deleted -- so a fence demanding they be scheduled is a fence arguing for
    the return of a book the principal closed.

    The invariant that replaces it is stronger and is the desk's actual topology: THIS LINUX BOX
    HAS NO ORDER PATH AT ALL. The money path is desks/mt5/ on the Windows host, behind the MT5
    terminal's own broker session. A research box that cannot place an order cannot place a wrong
    one, however badly its code fails.
    """
    for path in (CYCLE, CRON):
        src = _active(path.read_text("utf-8"))
        back = [s for s in _RETIRED_ORDER_PATH if s in src]
        assert back == [], (
            f"{path} schedules {back} -- the retired crypto-exchange order path. The universe "
            "mandate (2026-08-18) closed that venue and these scripts are deleted; this box "
            "executes nothing. The MT5 money path is desks/mt5/mt5desk/gateway.py.")
        assert "--place" not in src, (
            f"{path} carries a live order-placing flag. Nothing scheduled on this host may place "
            "an order.")


def test_ANY_SCHEDULED_SPENDER_READS_ITS_DENOMINATOR_RATHER_THAN_TYPING_IT() -> None:
    """THE LESSON OUTLIVES THE VENUE, so it is kept as a rule about any future spender rather than
    deleted with the crypto executors it was written for.

    A hand-typed denominator is right when it is typed and wrong when it is used. 2026-08-15:
    sized at `--equity 198` against a balance that had already lost the conversion spread -- two
    legs filled, the third refused for insufficient balance, the account left two-thirds invested.
    So: a literal `--equity`/`--balance` figure may never appear on a scheduled line. `auto` is the
    only accepted value, because it is read from the venue at the moment it is used.

    SCOPE, DELIBERATELY NARROW. This pins the ORDER-SIZING denominator, not every number that
    happens to be money-shaped. A first draft also matched `--capital` and immediately fired on
    `scripts/run_auto_promotion.py --capital 200` in the cron pipeline -- which is a promotion
    THRESHOLD, not a size sent to a venue, and reads from no balance. Widening a fence until it
    catches the wrong thing is how a real rule gets diluted into an ignored one. (That literal is
    still worth a look on its own terms; it is simply not this fence's finding.)
    """
    bad_literal = re.compile(r"--(?:equity|balance)[= ]+[0-9]")
    for path in (CYCLE, CRON):
        for ln in _active(path.read_text("utf-8")).split("\n"):
            assert not bad_literal.search(ln), (
                f"{path}: a scheduled line types its own denominator -- {ln.strip()[:90]!r}. It "
                "is correct when typed and wrong when used; read it from the venue (`auto`).")


CRON = Path("scripts/daily_research_cycle.py")


def test_THE_SURVIVING_STAGES_ARE_IN_THE_PIPELINE_THAT_ACTUALLY_FIRES() -> None:
    """MEASURED 2026-08-15, and the finding still binds. Two daily pipelines exist on the box: the
    2am root crontab runs scripts/daily_research_cycle.py, and ops/run_research_cycle.sh is driven
    by a USER systemd unit -- which does not fire at all unless lingering is enabled for the
    account. Work wired only into the shell cycle was scheduled in a file whose scheduler could
    not be demonstrated: III.16 wearing a cron entry's clothes.

    NARROWED 2026-09-05. The original list was the crypto order path -- run_spot_momentum,
    run_spot_executor, run_discretionary_live -- and those are deleted with the retired venue, so
    demanding them here would demand the book's return. What remains of the list is the part that
    was never venue-specific: promotion must run, and the ladder that feeds it must run, in the
    pipeline whose scheduler is demonstrable.
    """
    src = _active(CRON.read_text("utf-8"))
    for stage in ("run_auto_promotion.py", "run_live_ladder.py"):
        assert stage in src, (
            f"{stage} is not in the pipeline the crontab runs -- it fires only if a user timer "
            "happens to be enabled, and nobody would notice the day it is not")


def test_THE_LADDER_RUNS_BEFORE_PROMOTION_IN_BOTH_PIPELINES() -> None:
    """A promotion decided from a pre-ladder read cites Stage-B figures the dashboard never
    showed, which makes it unauditable after the fact."""
    for path in (CYCLE, CRON):
        src = path.read_text("utf-8")
        if "run_auto_promotion.py" not in src:
            continue
        assert src.index("run_live_ladder.py") < src.index("run_auto_promotion.py"), (
            f"{path}: promotion runs before the ladder that produces its inputs")


# RETIRED 2026-09-05: `test_THE_SCHEDULED_DENOMINATORS_ARE_READ_NOT_TYPED` asserted that
# `run_spot_executor.py` and `run_discretionary_live.py` in scripts/daily_research_cycle.py each
# carried `--equity auto`. Both scripts are deleted with the crypto-exchange desk, so the fence
# indexed for a substring that no longer exists and raised ValueError rather than failing an
# assertion -- a fence that errors instead of asserting is a fence nobody can read the verdict of.
# Its rule was not lost: `test_ANY_SCHEDULED_SPENDER_READS_ITS_DENOMINATOR_RATHER_THAN_TYPING_IT`
# above now enforces it across BOTH pipelines and against ANY future spender, rather than against
# two named crypto scripts -- which is the form the 2026-08-15 `--equity 198` incident actually
# argues for.
