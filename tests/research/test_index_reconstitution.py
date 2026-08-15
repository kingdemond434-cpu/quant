"""Index reconstitution flow -- census gap #1 (0.48, NO-CANDIDATE), pre-registered before any fetch.

An index change is a dated, pre-announced, price-insensitive order of known direction and
approximately known size. These tests pin the three things that decide whether the screen measures
that mechanism or manufactures it: the alignment rule, the benchmark, and what it does when it
cannot form a window.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from libs.research.index_reconstitution import (
    MIN_EVENTS,
    N_CONSTRUCTIONS,
    ReconEvent,
    event_excess_return,
    run_screen,
    window_return,
)

_BASE = datetime(2026, 1, 1, tzinfo=UTC)
_STAMPS = tuple(_BASE + timedelta(days=i) for i in range(200))


def _flat(v: float = 100.0) -> tuple[tuple[datetime, ...], np.ndarray]:
    return _STAMPS, np.full(len(_STAMPS), v, dtype="float64")


def test_ENTRY_IS_STRICTLY_AFTER_THE_ANNOUNCEMENT() -> None:
    """THE ALIGNMENT RULE, AND IT IS THE WHOLE STUDY. An announcement is public at a MOMENT, not
    on a date. Entering on the announcement day's own close puts the position on the bar carrying
    the news and manufactures the effect being measured -- the error that has killed more event
    studies on this desk than any other."""
    closes = np.full(len(_STAMPS), 100.0)
    closes[10] = 130.0                      # the announcement bar itself jumps
    closes[11:] = 130.0
    r = window_return(_STAMPS, closes, _STAMPS[10], _STAMPS[20])
    assert r == 0.0, "the announcement bar's own move must not be captured"
    # a move that happens AFTER the announcement is the thing being measured, and must be
    closes2 = np.full(len(_STAMPS), 100.0)
    closes2[12:] = 110.0
    assert window_return(_STAMPS, closes2, _STAMPS[10], _STAMPS[20]) > 0.09


def test_AN_UNFORMABLE_WINDOW_IS_NONE_AND_NEVER_ZERO() -> None:
    """A window that could not be formed is UNMEASURED. Returning 0.0 would enter the sample as a
    real observation of no effect and drag the mean toward the null with fabricated data."""
    stamps, closes = _flat()
    assert window_return(stamps, closes, _STAMPS[-1], _STAMPS[-1]) is None
    assert window_return((), np.array([]), _STAMPS[0], _STAMPS[5]) is None
    assert window_return(_STAMPS, closes, _STAMPS[20], _STAMPS[10]) is None, "end before start"


def test_THE_RETURN_IS_IN_EXCESS_OF_THE_NON_CHANGING_MEMBERS() -> None:
    """An index add during a rally is not evidence of anything. The market factor is exactly what
    both legs share, and differencing it away is what separates a flow claim from a beta claim."""
    up = np.linspace(100.0, 120.0, len(_STAMPS))
    panel = {"ADD": (_STAMPS, up.copy()), "P1": (_STAMPS, up.copy()), "P2": (_STAMPS, up.copy())}
    ev = ReconEvent("ADD", "IDX", _STAMPS[10], _STAMPS[20], +1)
    r = event_excess_return(ev, panel, ["P1", "P2"], start=ev.announced_at, end=ev.effective_at)
    assert r is not None and abs(r) < 1e-9, "moving exactly with its peers is zero excess"


def test_A_DELETE_IS_SIGNED_SO_BOTH_LEGS_POOL() -> None:
    """direction=-1 means the forced order is a SELL. Pooling adds and deletes without the sign
    would cancel a real effect against itself and report a null."""
    down = np.full(len(_STAMPS), 100.0)
    # the fall starts AFTER the entry bar (index 11), so it is inside the measured window rather
    # than on the bar the position is taken at -- the alignment rule applies to this test too
    down[13:] = 90.0
    panel = {"DEL": (_STAMPS, down), "P1": _flat()}
    ev = ReconEvent("DEL", "IDX", _STAMPS[10], _STAMPS[20], -1)
    r = event_excess_return(ev, panel, ["P1"], start=ev.announced_at, end=ev.effective_at)
    assert r is not None and r > 0, "a delete that falls is a WIN for the short leg"


def test_NO_BENCHMARK_MEANS_NO_RESULT() -> None:
    """A raw return published as an excess return is the same defect as a missing benchmark, one
    step later."""
    panel = {"ADD": _flat()}
    ev = ReconEvent("ADD", "IDX", _STAMPS[10], _STAMPS[20], +1)
    assert event_excess_return(ev, panel, [], start=ev.announced_at, end=ev.effective_at) is None


def test_A_SMALL_SAMPLE_IS_UNDERPOWERED_AND_NEVER_REFUTED() -> None:
    """A null on a sample too small to detect the effect is a statement about the SAMPLE. Recording
    it as a kill would retire the desk's highest-ranked mechanism on no evidence (L1.28a)."""
    panel = {f"P{i}": _flat() for i in range(4)}
    panel["A0"] = _flat()
    evs = [ReconEvent("A0", "IDX", _STAMPS[10], _STAMPS[20], +1)]
    rep = run_screen(evs, panel, benchmark=[f"P{i}" for i in range(4)])
    assert rep["status"] == "UNDERPOWERED" and rep["verdict"] == "UNMEASURED"
    assert "NOT REFUTED" in rep["why"] and str(MIN_EVENTS) in rep["why"]


def test_A_DEGENERATE_SAMPLE_IS_UNMEASURED_AND_NEVER_REFUTED() -> None:
    """Zero dispersion means the standard error is zero and t does not exist. Folding that into
    "below the bar" publishes a REFUTED verdict for a sample that is degenerate rather than null,
    and it reads identically to a real kill everywhere downstream."""
    stamps = _STAMPS
    panel: dict[str, tuple[tuple[datetime, ...], np.ndarray]] = {
        f"P{i}": (stamps, np.full(len(stamps), 100.0)) for i in range(3)}
    evs = []
    for k in range(30):
        a_i, e_i = 10 + k * 4, 15 + k * 4
        arr = np.full(len(stamps), 100.0)
        arr[a_i + 1:] = 103.0                      # IDENTICAL for every event -> zero variance
        panel[f"A{k}"] = (stamps, arr)
        evs.append(ReconEvent(f"A{k}", "IDX", stamps[a_i], stamps[e_i], +1, weight_change=0.01))
    rep = run_screen(evs, panel, benchmark=[f"P{i}" for i in range(3)])
    assert rep["status"] == "DEGENERATE" and rep["verdict"] == "UNMEASURED"
    assert "NOT refuted" in rep["why"]


def test_NO_PANEL_IS_NO_RESULT_NOT_A_NULL() -> None:
    rep = run_screen([ReconEvent("A", "IDX", _STAMPS[1], _STAMPS[5], +1)], {})
    assert rep["verdict"] == "UNMEASURED" and "not a null result" in rep["why"]


def test_DRIFT_WITHOUT_REVERSAL_IS_NOT_A_FLOW_RESULT() -> None:
    """THE CONSTRUCTION PAIR THAT MAKES THIS A MECHANISM TEST. If C1 is real flow compensation,
    part of it must give back. An inclusion effect that never reverses is more likely a value
    story, and reporting it as a win for THIS class would credit the desk with a mechanism it did
    not demonstrate."""
    stamps = _STAMPS
    panel: dict[str, tuple[tuple[datetime, ...], np.ndarray]] = {
        f"P{i}": (stamps, np.full(len(stamps), 100.0)) for i in range(5)}
    evs = []
    for k in range(30):
        a_i, e_i = 10 + k * 4, 15 + k * 4
        # jittered per event: a sample with ZERO dispersion has no t at all, which the screen
        # correctly reports as DEGENERATE rather than as a kill
        bump = 1.03 + 0.004 * ((k % 5) - 2)
        arr = np.full(len(stamps), 100.0)
        arr[a_i + 1:e_i + 1] = np.linspace(100.0, 100.0 * bump, e_i - a_i)
        arr[e_i + 1:] = 100.0 * bump               # rises and NEVER gives back
        panel[f"A{k}"] = (stamps, arr)
        evs.append(ReconEvent(f"A{k}", "IDX", stamps[a_i], stamps[e_i], +1, weight_change=0.01))
    rep = run_screen(evs, panel, benchmark=[f"P{i}" for i in range(5)])
    assert rep["status"] == "RUN"
    assert rep["verdict"] == "ANOMALY-NOT-FLOW"
    assert "value story" in rep["why"]


def test_IT_CHARGES_ITS_OWN_FAMILYS_MULTIPLICITY_AND_NO_OTHERS() -> None:
    """Three constructions, corrected within index_reconstitution_flow. Admitting this screen
    costs no other family anything -- that is the entire point of the partition."""
    from libs.validation.family_multiplicity import bh_bar, family_of

    rep = run_screen([], {"P": _flat()})
    assert rep["constructions"] == N_CONSTRUCTIONS == 3
    assert rep["holm_bar_within_family"] == bh_bar(3, 1)
    assert family_of("index_reconstitution_flow") == "index_reconstitution_flow"


def test_AN_INVALID_EVENT_IS_DROPPED_NOT_COERCED() -> None:
    """An effective date before its announcement is a parsing error in the methodology document.
    Coercing it -- swapping the dates, or taking the absolute window -- would invent an event."""
    assert not ReconEvent("A", "I", _STAMPS[20], _STAMPS[10], +1).valid
    assert not ReconEvent("A", "I", _STAMPS[10], _STAMPS[20], 0).valid
    assert not ReconEvent("", "I", _STAMPS[10], _STAMPS[20], +1).valid
    assert ReconEvent("A", "I", _STAMPS[10], _STAMPS[20], -1).valid
