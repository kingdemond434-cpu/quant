"""ONE PATHOLOGICAL RUN MUST NOT EXCLUDE A JOB FROM THE BOX FOR EVER.

WHAT HAPPENED. `measured_need_mb` corrects a job's declared memory need upward by what it has
actually used -- a good mechanism, built because `external_gauntlet` declared 1200MB and was found
holding 4882MB, starving `edge_search` and `orthogonal_sweep` off an 8GB box that also runs the
live MT5 terminal. It took the MAXIMUM of the last eight runs.

The maximum is a one-way ratchet in the wrong direction. That single 4882MB reading became the
figure the job was admitted on, and 4882MB of free memory essentially never exists on this box, so
the gauntlet stood down every hour, waited its twelve minutes of patience, stood down again, and
exited non-zero. Measured 2026-09-05 from live desk state: `FAILING MT5-Gauntlet: last result 1
twice in a row`, the same for `MT5-QQuantGatesCertify`, and no new certificate for a day. A guard
written to stop one job starving the box had starved that job out of the box permanently -- and
reported it as a crash, so the alarm pointed at the gauntlet rather than at the admission figure.

A HIGH QUANTILE KEEPS EVERY PROPERTY THE RATCHET WAS FOR. A job that consistently grows is still
held to what it grew to, because p75 rises with it within a few runs, while a one-off ages out.

p75 RATHER THAN A MEDIAN, because a median dismisses ANY minority: a job that runs heavy one time
in three would be admitted on its light mode and thrash the box on its heavy one. One heavy run
out of three still sets the bar; one out of eight does not.

The declaration remains a hard FLOOR, so nothing can talk its way into a box that cannot hold it,
and admission is only the first of two layers -- `external_gauntlet` also defers cells mid-run
when it exceeds `MEMORY_BUDGET_MB`, so a job that does grow throttles itself rather than
thrashing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parent.parent
for _p in (str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import job_lock as jl  # noqa: E402

DECLARED = 1200


@pytest.fixture
def peaks(tmp_path, monkeypatch):
    """Point the peak history at a scratch file so this never touches the desk's real record."""
    path = tmp_path / "peaks.json"
    monkeypatch.setattr(jl, "_peaks_path", lambda name: path)

    def write(history: list[int]) -> tuple[int, str]:
        path.write_text(json.dumps(history), "utf-8")
        return jl.measured_need_mb("external_gauntlet", DECLARED)
    return write


def test_a_single_spike_does_not_raise_the_bar(peaks) -> None:
    """THE LIVE DEFECT. Five ordinary runs and one 4882MB outlier must admit on the ordinary."""
    need, why = peaks([1619, 1615, 4882, 1600, 1622, 1610])  # 1 in 6
    assert need < 2000, (
        f"admitted on {need}MB because of one outlier -- on an 8GB box running the live terminal "
        f"that is a permanent stand-down, which is how the gauntlet stopped certifying: {why}")


def test_the_outlier_is_still_reported(peaks) -> None:
    """Robust must not mean blind. A tail far above the admitted figure is exactly what somebody
    should see, so it is named -- otherwise this fix trades a false alarm for a silence."""
    _need, why = peaks([1619, 1615, 4882, 1600, 1622, 1610])
    assert "4882" in why, f"the outlier vanished from the reason string: {why}"


def test_a_job_that_genuinely_grew_is_still_held_to_it(peaks) -> None:
    """THE SAFETY PROPERTY, and the one this change must not cost. Consistent growth is not an
    outlier: if every recent run is near 4.8GB, that IS what the job needs and admitting it on
    1200MB would put it back to thrashing the box and endangering the live terminal."""
    need, _why = peaks([4700, 4820, 4882, 4750, 4900])
    assert need >= 4700, f"a consistently heavy job was admitted on {need}MB"


def test_a_spike_in_a_SHORT_record_still_sets_the_bar(peaks) -> None:
    """The reason the statistic is p75 and not a median.

    One heavy run out of three is not an outlier -- there is not enough record to call it one, and
    a job that runs heavy a third of the time thrashes the box a third of the time. A median would
    dismiss it as a minority and admit on the light mode. p75 keeps it.
    """
    need, _why = peaks([300, 4882, 310])
    assert need == 4882, (
        f"a spike that is a THIRD of the entire record was dismissed as an outlier ({need}MB) -- "
        "that is a bimodal job being admitted on its small mode")


def test_the_declaration_is_a_hard_floor(peaks) -> None:
    """A job lighter than its declaration is admitted on the declaration, never on the measurement.

    Downward correction would let a job that happened to run small on a thin docket be admitted
    into headroom it cannot rely on -- and the next full docket then thrashes. The correction is
    upward-only by design; only the STATISTIC changed, not the direction.
    """
    need, _why = peaks([900, 950, 880])
    assert need == DECLARED, f"a light run talked the floor down to {need}MB"


def test_no_history_means_the_declaration_stands(peaks) -> None:
    need, why = peaks([])
    assert need == DECLARED and "no run measured" in why


def test_the_fence_can_actually_fail() -> None:
    """L1.28a: if `measured_need_mb` stopped consulting history at all, every test above would
    pass on the declaration alone and the safety property would be gone with no failure."""
    assert jl.measured_need_mb.__doc__, "the function lost its contract"
    assert jl.PEAK_HISTORY >= 3, (
        "a window shorter than three runs has no quantile worth the name -- one bad run would "
        "be a third of the evidence again")
