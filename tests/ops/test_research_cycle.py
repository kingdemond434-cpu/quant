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
SERVICE = Path("ops/quant-research.service")
TIMER = Path("ops/quant-research.timer")


def test_THE_EXECUTION_STAGE_IS_SCHEDULED_AT_ALL() -> None:
    """The finding this closes: mining was automated, testing was not."""
    assert CYCLE.exists() and SERVICE.exists() and TIMER.exists()
    assert "run_research_cycle.sh" in SERVICE.read_text("utf-8")
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


def test_THE_TIMER_AVOIDS_THE_MINER_WINDOW() -> None:
    """Seven regional digs and a sweep contending for the same 4GB is how a box that OOM-killed
    moat_screen loses both."""
    assert "04:00" in TIMER.read_text("utf-8")
    assert "Persistent=true" in TIMER.read_text("utf-8"), (
        "a missed cycle should run on the next boot rather than being skipped silently")


def test_THE_BAR_BUDGET_IS_OVERRIDABLE_BUT_HAS_A_SANE_DEFAULT() -> None:
    """build_bars streams now, so memory is O(buckets) -- but the budget still costs wall time and
    competes with the recorders, so it is a declared default rather than an unbounded job."""
    src = CYCLE.read_text("utf-8")
    assert 'BARS_FILE_BUDGET:-' in src
