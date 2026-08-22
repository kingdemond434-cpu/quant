"""THE RESEARCH CYCLE -- the desk automated every generator and left execution manual.

MEASURED 2026-08-08: nine systemd timers, every one of them a MINER. Nothing scheduled the bar
build or a single study. So the stage the desk's own funnel diagnosis calls the bottleneck
(EXECUTION) was the only stage a human had to type, while the stages it says are NOT the constraint
ran daily and unattended.

That is L1.52(a)'s asymmetry inverted -- `queue backlogged -> EXECUTE` -- and it is why the desk
could hold 898,560 candidates against 0 executed trials for weeks without anything looking broken.
"""

from __future__ import annotations

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


def test_THE_LEADERBOARD_PANEL_ACCUMULATES_ON_A_SCHEDULE() -> None:
    """III.15 needs CALENDAR SEPARATION and nothing else can manufacture it.

    screen_copytrading refuses to publish a persistence number until it holds two cohort snapshots
    at least five days apart, with exits counted as failures -- the only unbiased design against a
    leaderboard, which is by construction the maximum of a very large number of draws. It was
    written 2026-07-31 with ZERO schedulers, so the panel accumulated nothing and its NO-DATA was a
    statement about the cron table rather than about copy traders (III.16, L1.28a).

    A screen whose verdict depends on repeated snapshots and which nothing repeats is not a screen.
    """
    assert "screen_copytrading.py" in CYCLE.read_text("utf-8"), (
        "the copytrading/leaderboard forward panel is not scheduled -- it will report NO-DATA "
        "forever, and the reason will be the scheduler rather than the evidence")


def test_THE_ORDER_PATH_IS_SCHEDULED() -> None:
    """III.16 on the one capability that touches money. Everything else in the cycle computes what
    the book SHOULD be; without this line the desk publishes a correct target every night and holds
    yesterday's positions forever."""
    src = CYCLE.read_text("utf-8")
    assert "run_spot_executor.py" in src, "the book is computed daily and never placed"
    assert "--place" in src, "a scheduled executor without --place is a nightly dry run"


def test_THE_SCHEDULED_EQUITY_IS_READ_NOT_TYPED() -> None:
    """A hand-typed denominator is right when it is typed and wrong when it is used. 2026-08-15:
    sized at $198 against a balance that had already lost the conversion spread -- two legs filled,
    the third refused for insufficient balance, account left two-thirds invested."""
    src = CYCLE.read_text("utf-8")
    i = src.index("run_spot_executor.py")
    assert "--equity auto" in src[i:i + 200], (
        "the scheduled run must read equity from the venue; a literal would go stale on the first "
        "fill and nobody would be watching")


CRON = Path("scripts/daily_research_cycle.py")


def test_THE_MONEY_PATH_IS_IN_THE_PIPELINE_THAT_ACTUALLY_FIRES() -> None:
    """MEASURED 2026-08-15. Two daily pipelines exist on the box: the 2am root crontab runs
    scripts/daily_research_cycle.py, and ops/run_research_cycle.sh is driven by a USER systemd unit
    -- which does not fire at all unless lingering is enabled for the account.

    Everything touching capital had been wired into the shell cycle alone. `systemctl list-timers`
    showed no unit for it. So the order path, the promotion verb and the leaderboard panel were
    scheduled in a file whose scheduler could not be demonstrated, which is III.16 wearing a cron
    entry's clothes.
    """
    src = CRON.read_text("utf-8")
    for stage in ("run_spot_momentum.py", "run_spot_executor.py", "run_auto_promotion.py",
                  "run_live_ladder.py", "run_discretionary_live.py"):
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


def test_THE_SCHEDULED_DENOMINATORS_ARE_READ_NOT_TYPED() -> None:
    """The literal that broke the first live book was `--equity 198`. Anything spending money on a
    schedule reads its denominator from the venue."""
    src = CRON.read_text("utf-8")
    i = src.index("run_spot_executor.py")
    assert "--equity auto" in src[i:i + 120]
    j = src.index("run_discretionary_live.py")
    assert "--equity auto" in src[j:j + 120]
