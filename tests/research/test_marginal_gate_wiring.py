"""R0480 -- the marginal-contribution gate WIRED into paper_sleeves.decide().

The live forward-slot path never consulted correlation at all: slot_admission ranks by
time-to-resolution and the only dedupe is NAME-based, so a differently-named candidate at
rho 0.97 to the book read as 'fresh' and took a scarce Holm slot. These tests pin the four
R0480 requirements:

  (1) the incumbent matrix is assembled from the standing clocks' own series,
  (2) series are inner-JOINED on identical timestamps before evaluate() -- which truncates from
      the front and does not join, so misalignment silently produces a meaningless rho,
  (3) an unresolvable incumbent reads UNMEASURED and fails CLOSED to rho=1, NAMED, never dropped
      from the matrix; an unresolvable candidate against a standing book fails the same way,
  (4) the Admission verdict is persisted beside the spawn/queue row (covered on the organ path in
      test_paper_sleeves.test_ONE_IDLE_PLUS_ONE_DEAD_SLOT...).

Plus the one deliberate pass-through: an EMPTY book with no candidate series is NOT-APPLICABLE --
refusing a zero-capital clock for lacking the series the clock exists to produce would be the
circular gate the two-stage law forbids.
"""
from __future__ import annotations

import numpy as np

from libs.research.paper_sleeves import Candidate, decide, marginal_gate

_DAY_NS = 86_400_000_000_000
_T0 = np.datetime64("2026-01-01T00:00:00", "ns").astype(np.int64)


def _series(returns: np.ndarray, start_bar: int = 0) -> tuple[np.ndarray, np.ndarray]:
    t = _T0 + (start_bar + np.arange(len(returns), dtype=np.int64)) * _DAY_NS
    return t, np.asarray(returns, dtype=float)


def _rng():
    return np.random.default_rng(20260818)


class TestFailClosed:
    def test_unresolvable_incumbent_refuses_and_is_named(self):
        """Requirement 3: None in the map -> rho=1, refusal names the clock, never drops it."""
        rng = _rng()
        cand = _series(rng.normal(0.003, 0.01, 400))
        v = marginal_gate(cand, {"good_clock": _series(rng.normal(0.001, 0.01, 400)),
                                 "axis_clock_no_series": None})
        assert v["admitted"] is False
        assert v["rho_used"] == 1.0, "fail closed to rho=1, marginal_admission's own blank"
        assert "axis_clock_no_series" in v["reason"], "the unresolvable incumbent must be NAMED"

    def test_unresolvable_candidate_against_a_book_refuses(self):
        rng = _rng()
        v = marginal_gate(None, {"inc": _series(rng.normal(0.001, 0.01, 400))})
        assert v["admitted"] is False and v["rho_used"] == 1.0
        assert "candidate" in v["reason"].lower()

    def test_empty_book_with_no_series_is_not_applicable_pass(self):
        """The circular-gate exception: nothing to duplicate, no invented numbers."""
        v = marginal_gate(None, {})
        assert v["admitted"] is True
        assert v.get("gate") == "NOT-APPLICABLE"
        assert "rho_used" not in v, "a vacuous verdict must not manufacture a measurement"


class TestMeasuredVerdicts:
    def test_a_duplicate_of_the_book_is_refused(self):
        rng = _rng()
        r = rng.normal(0.001, 0.01, 400)
        v = marginal_gate(_series(r), {"inc": _series(r)})   # the SAME series, renamed
        assert v["admitted"] is False
        assert v["rho_used"] > 0.99, f"a renamed duplicate must read as the book: {v['reason']}"

    def test_an_orthogonal_stronger_candidate_is_admitted(self):
        rng = _rng()
        v = marginal_gate(_series(rng.normal(0.003, 0.01, 400)),
                          {"inc": _series(rng.normal(0.0008, 0.01, 400))})
        assert v["admitted"] is True, v["reason"]
        assert v["gain"] >= 0.02

    def test_alignment_is_a_join_not_a_front_truncation(self):
        """Requirement 2, proven by a verdict FLIP.

        Candidate and incumbent are the SAME returns over the same 200 calendar days, but the
        incumbent's array carries 200 extra leading bars. A front-truncation compares desynced
        rows (rho ~ 0 -> would admit the duplicate); the timestamp join compares the overlap
        (rho = 1 -> refused). Only one of those is a measurement.
        """
        rng = _rng()
        shared = rng.normal(0.002, 0.01, 200)
        lead_in = rng.normal(0.0, 0.01, 200)
        cand = _series(shared, start_bar=200)
        inc = _series(np.concatenate([lead_in, shared]), start_bar=0)
        v = marginal_gate(cand, {"inc": inc})
        assert v["n_overlap"] == 200, "the join must find exactly the common timestamps"
        assert v["admitted"] is False and v["rho_used"] > 0.99, (
            f"a duplicate hidden by offset arrays must still read as the book: {v['reason']}")

    def test_disjoint_timestamps_refuse_on_overlap(self):
        rng = _rng()
        v = marginal_gate(_series(rng.normal(0.002, 0.01, 100), start_bar=0),
                          {"inc": _series(rng.normal(0.001, 0.01, 100), start_bar=500)})
        assert v["admitted"] is False
        assert v["n_overlap"] == 0


class TestDecideWiring:
    def _cand(self, name: str) -> Candidate:
        return Candidate(name=name, axis="x", trial=name, ic_t=3.0, ic=0.05, horizon_days=1.0,
                         n_eff=400.0, source_kind="full_sweep_npz", pnl_key=name)

    def _cohort(self, slots: list[str], free: int = 3) -> dict:
        return {"m_concurrent": 12 - free, "m_upper": 12 - free, "cap": 12, "complete": True,
                "over_cap": False, "idle_slots": free,
                "slots": [{"name": n} for n in slots]}

    def test_refused_candidate_is_queued_with_its_verdict_never_dropped(self):
        rng = _rng()
        book = rng.normal(0.001, 0.01, 400)
        series = {"dup": _series(book), "fresh": _series(rng.normal(0.003, 0.01, 400))}
        d = decide([self._cand("dup"), self._cand("fresh")], set(),
                   self._cohort(["inc"]),
                   series_of=lambda c: series[c.name],
                   incumbent_series={"inc": _series(book)})
        assert [c.name for c in d["spawn"]] == ["fresh"]
        assert "dup" in [c.name for c in d["queue"]], "a refusal queues, it never vanishes"
        assert d["admissions"]["dup"]["admitted"] is False
        assert d["admissions"]["fresh"]["admitted"] is True

    def test_default_callers_fail_closed_when_slots_stand(self):
        """No series channel + a standing book = refuse. Absence must never read as permission."""
        d = decide([self._cand("c")], set(), self._cohort(["standing_clock"]))
        assert d["spawn"] == []
        assert d["admissions"]["c"]["admitted"] is False
        assert "standing_clock" in d["admissions"]["c"]["reason"]

    def test_incumbent_set_comes_from_the_cohorts_own_slots(self):
        """Requirement 1+3: a slot missing from the provided map reads UNMEASURED -- the map
        cannot silently shrink the matrix by omitting a clock."""
        rng = _rng()
        d = decide([self._cand("c")], set(), self._cohort(["known", "unknown_to_map"]),
                   series_of=lambda c: _series(rng.normal(0.003, 0.01, 400)),
                   incumbent_series={"known": _series(rng.normal(0.001, 0.01, 400))})
        assert d["spawn"] == []
        assert "unknown_to_map" in d["admissions"]["c"]["reason"]
