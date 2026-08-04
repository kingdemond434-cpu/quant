"""Information-value accounting -- the surprise metric that had stopped measuring surprise.

triage #39 filed this engine as "exists but DEAD -- repair the estimator", on the evidence that
`info_bits` was a constant 0.2345 across all 810 logged rows. The estimator was never broken:
0.2345 is exactly -log2(0.85), so every caller was passing the same hardcoded prior of 0.15. A
prior that never updates produces identical surprise for every outcome, which makes total_bits
precisely `n x 0.2345` -- a ROW COUNT wearing an information-theory unit.

That is the third instance in one session of a counter dressed as evidence, after §33's
min_snapshots (which counted auditor invocations) and the allocator's closure-rate n (60
observations across 5 hours). This one erred in the flattering direction: with a measured record
of 420/420 rejections, booking each rejection as 0.2345 bits against a 0.15 prior records the desk
as LEARNING from the outcome it should most have expected.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.research.information_value import (
    COLD_START_PRIOR,
    empirical_prior,
    record_factory_cycle,
    summary,
    surprise_bits,
)


def test_surprise_is_higher_for_the_less_expected_outcome() -> None:
    """The property the whole metric rests on, asserted before anything that depends on it."""
    assert surprise_bits(0.15, survived=True) > surprise_bits(0.15, survived=False)


def test_an_empty_log_reports_zero_experiments_not_an_error(tmp_path) -> None:
    assert summary(log=tmp_path / "none.jsonl")["experiments"] == 0


class TestLearnedPrior:
    """triage #39: `info_bits` was constant 0.2345 across all 810 rows.

    The row was filed as "Information Gain Engine (exists but DEAD) -- repair the estimator". The
    estimator was never broken. 0.2345 is exactly -log2(0.85), so every caller passed the same
    hardcoded prior of 0.15; a prior that never updates yields identical surprise for every
    outcome, which makes total_bits precisely `n x 0.2345` -- a ROW COUNT wearing an
    information-theory unit. Third instance in one session of a counter dressed as evidence.

    And it erred in the flattering direction: the desk's measured record is 420/420 rejections, so
    booking each rejection as 0.2345 bits of surprise against a 0.15 prior records the desk as
    learning from an outcome that was exactly what it should have expected.
    """

    def test_the_prior_is_learned_from_the_desk_own_record(self, tmp_path) -> None:
        log = tmp_path / "iv.jsonl"
        assert empirical_prior(log)[0] == COLD_START_PRIOR
        record_factory_cycle(40, 0, log=log, web=tmp_path / "w.json")
        p, why = empirical_prior(log)
        assert p < COLD_START_PRIOR, "40 rejections must move the prior DOWN"
        assert "EMPIRICAL" in why and "40 logged" in why

    def test_info_bits_stops_being_constant(self, tmp_path) -> None:
        """The observable symptom, asserted directly: two cycles at different priors must produce
        different surprise. Identical values across every row is the defect, not the metric."""
        log, web = tmp_path / "iv.jsonl", tmp_path / "w.json"
        record_factory_cycle(40, 0, log=log, web=web)
        record_factory_cycle(40, 0, log=log, web=web)
        vals = {json.loads(x)["info_bits"] for x in log.read_text("utf-8").splitlines() if x}
        assert len(vals) > 1, f"info_bits is still constant: {vals}"

    def test_a_rejection_the_desk_EXPECTS_carries_almost_no_information(self, tmp_path) -> None:
        """The correction that matters. Under a learned prior a rejection is unsurprising, because
        it is what 420/420 predicts. Under the old constant it booked 0.2345 bits every time --
        roughly a sevenfold overstatement of learning, always in the desk's favour."""
        log, web = tmp_path / "iv.jsonl", tmp_path / "w.json"
        record_factory_cycle(60, 0, log=log, web=web)
        record_factory_cycle(1, 0, log=log, web=web)
        last = json.loads(log.read_text("utf-8").strip().splitlines()[-1])
        assert last["info_bits"] < 0.2345 / 2

    def test_a_zero_prior_is_smoothed_so_learning_never_reads_as_impossible(self, tmp_path) -> None:
        """Unsmoothed, 0 survivors in N gives a prior of exactly 0.0 -- every rejection becomes
        ZERO-surprise and the desk is recorded as learning nothing from any outcome, including
        from a survivor. The smoothing is what keeps the metric alive at the desk's real shape."""
        log = tmp_path / "iv.jsonl"
        record_factory_cycle(500, 0, log=log, web=tmp_path / "w.json")
        p, _ = empirical_prior(log)
        assert p > 0.0

    def test_the_prior_and_its_provenance_travel_with_the_number(self, tmp_path) -> None:
        """info_bits is meaningless without knowing what it was surprised RELATIVE TO. Reporting
        bits against an unstated prior is how 810 identical values read as accumulated
        information."""
        card = record_factory_cycle(10, 1, log=tmp_path / "iv.jsonl", web=tmp_path / "w.json")
        assert "prior_used" in card and "prior_basis" in card
        assert "COLD START" in card["prior_basis"]

    def test_an_explicit_prior_is_still_honoured(self, tmp_path) -> None:
        """A caller scoring against a stated counterfactual must still be able to. Only the
        DEFAULT changed -- from a hardcoded rate the desk has measured to be wrong, to its own."""
        card = record_factory_cycle(5, 0, base_prior=0.5,
                                    log=tmp_path / "iv.jsonl", web=tmp_path / "w.json")
        assert card["prior_used"] == 0.5
        assert card["prior_basis"] == "caller-supplied prior"
