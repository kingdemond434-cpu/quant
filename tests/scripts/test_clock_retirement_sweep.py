"""GAP 112: the reclamation logic existed and only a CHALLENGER could trigger it.

`plan_displacement` is always called WITH a queue -- a challenger arrives and a plan is computed
to make room. With an empty queue nothing calls it, so a clock that provably cannot resolve keeps
its seat and keeps charging every neighbour multiplicity for it.

Measured on the live box 2026-08-13: m=15 against a cap of 12, ZERO idle, bar 2.71 instead of
2.64, and `walcl_reserve_impulse` sitting DEGENERATE -- 9 dated rows yielding 2 distinct
observations, an instrument fault that cannot resolve however long it runs.

The load-bearing tests here are the two REFUSALS: the sweep must never retire anything itself, and
it must never propose a BLOCKED clock.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "crs", Path(__file__).resolve().parents[2] / "scripts" / "run_clock_retirement_sweep.py")
assert _SPEC and _SPEC.loader
_M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)


def _slot(name, *, state="ACCRUING", evidence="ACCRUING", days=10, verdict=""):
    return {"name": name, "state": state, "evidence": evidence, "days": days,
            "verdict": verdict, "kind": "axis"}


class TestItSurfacesWhatWasInvisible:
    def test_THE_LIVE_DEGENERATE_CLOCK_IS_PROPOSED(self) -> None:
        """The measured instance: an instrument fault holding a seat while the queue is empty."""
        slots = [_slot(f"live{i}") for i in range(14)]
        slots.append(_slot("walcl_reserve_impulse", state="DEGENERATE", evidence="ACCRUING",
                           days=2))
        rep = _M.sweep(slots)

        names = [p["clock"] for p in rep["proposals"]]
        assert "walcl_reserve_impulse" in names
        assert rep["over_cap"] is True and rep["m_now"] == 15
        assert rep["seats_free_now"] == 0
        assert rep["seats_freeable"] >= 1

    def test_it_reports_the_seats_that_would_come_back(self) -> None:
        """The number that decides whether this is worth doing: free seats AFTER retirement."""
        slots = [_slot(f"live{i}") for i in range(11)]
        slots += [_slot("dead1", state="DEGENERATE", days=1),
                  _slot("dead2", evidence="NO-EVIDENCE", days=0)]
        rep = _M.sweep(slots)
        assert rep["seats_freeable"] == 2
        assert rep["seats_free_if_all_retired"] == rep["cap"] - (rep["m_now"] - 2)

    def test_the_mechanism_of_death_travels_with_the_proposal(self) -> None:
        """L1.17: a refutation re-queued as untested buys the same dead axis again; an instrument
        fault filed as refuted retires ground nobody measured."""
        kill = "FAILING FORWARD -> kill candidate (Sharpe -0.42 on 61 observations, t=-1.83)"
        slots = [*[_slot(f"l{i}") for i in range(10)],
                 _slot("killed", verdict=kill, days=61),
                 _slot("jammed", state="DEGENERATE", days=1)]
        by = {p["clock"]: p["requeue_as"] for p in _M.sweep(slots)["proposals"]}
        assert by["killed"] == "REFUTED"
        assert by["jammed"] == "UNTESTED"

    def test_source_gone_is_freeable_and_requeues_as_untested(self) -> None:
        rep = _M.sweep([_slot("vanished", evidence="SOURCE-GONE", days=None)])
        assert rep["seats_freeable"] == 1
        assert rep["proposals"][0]["requeue_as"] == "UNTESTED"


class TestTheTwoRefusals:
    def test_IT_NEVER_RETIRES_ANYTHING_ITSELF(self) -> None:
        """Removing a row shrinks m and LOOSENS every remaining bar -- the phantom-edge direction.
        Retirement stays a ledgered decision, so every output is a PROPOSAL."""
        slots = [*[_slot(f"l{i}") for i in range(11)], _slot("dead", state="DEGENERATE", days=1)]
        rep = _M.sweep(slots)
        assert all("PROPOSED-RETIREMENT" in p["disposition"] for p in rep["proposals"])
        assert "ledgered decision" in rep["note"]
        assert rep["m_now"] == 12, "the sweep must not mutate the cohort it is reporting on"

    def test_A_BLOCKED_CLOCK_IS_NEVER_PROPOSED(self) -> None:
        """UNMEASURED means it cannot be ASSESSED, not that it is dead. Wrongly reclaiming
        destroys forward evidence that cannot be re-earned at any price; wrongly protecting costs
        a queue position, and those are not the same size of mistake."""
        slots = [*[_slot(f"l{i}") for i in range(11)],
                 _slot("unmeasurable", evidence="UNMEASURED", days=None)]
        rep = _M.sweep(slots)
        assert [p["clock"] for p in rep["proposals"]] == []
        assert [b["clock"] for b in rep["blocked"]] == ["unmeasurable"]

    def test_a_healthy_cohort_proposes_nothing(self) -> None:
        """NEGATIVE CONTROL. A sweep that always finds something to retire is a seat-harvesting
        machine, not a fence."""
        rep = _M.sweep([_slot(f"live{i}") for i in range(12)])
        assert rep["proposals"] == []
        assert len(rep["protected"]) == 12
        assert rep["over_cap"] is False
