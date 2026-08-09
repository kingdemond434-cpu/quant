"""THE CORPUS LEDGER'S TESTS — the two claims that would rot if unpinned.

  1. "we mined that practitioner" must be impossible to say without per-axis evidence AND a date
  2. a large claimed return must move READING ORDER and nothing else

The second is the one that decays quietly. It is very easy for an investigation-priority score to
start being cited as credibility, and the module's only defence is that no other score exists.
`test_THERE_IS_NO_CREDIBILITY_SCORE` pins that absence deliberately.
"""

from __future__ import annotations

import pytest

from libs.research import practitioner_corpus as pc
from libs.research.practitioner_corpus import (
    EXTRACTION_AXES,
    SYSTEMATIC_STATUS,
    Disagreement,
    PractitionerRecord,
    currently_exhausted,
    disagreement_hypotheses,
    effective_independent_sources,
    investigation_priority,
    source_roi,
    summarise,
)


def _rec(pid: str = "p1", **kw: object) -> PractitionerRecord:
    base: dict[str, object] = {"practitioner_id": pid, "name": pid.title(),
                               "systematic_status": "CONFIRMED_SYSTEMATIC",
                               "evidence_class": "VERIFIED"}
    base.update(kw)
    return PractitionerRecord(**base)                             # type: ignore[arg-type]


class TestRecord:
    def test_unknown_status_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown systematic_status"):
            PractitionerRecord(practitioner_id="x", systematic_status="LEGEND")

    def test_unknown_axis_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown extraction axis"):
            PractitionerRecord(practitioner_id="x", axes_extracted=("vibes",))

    def test_every_status_constructs(self) -> None:
        for s in SYSTEMATIC_STATUS:
            assert PractitionerRecord(practitioner_id="x", systematic_status=s)

    def test_process_axes_are_counted_separately_from_the_rules(self) -> None:
        rules_only = _rec(axes_extracted=("signal", "sizing", "execution"))
        assert rules_only.process_axes_covered == 0
        both = _rec(axes_extracted=("signal", "research_process", "retirement_process"))
        assert both.process_axes_covered == 2


class TestExhaustion:
    def test_an_unenumerated_corpus_can_never_be_exhausted(self) -> None:
        done, why = currently_exhausted(_rec())
        assert done is False
        assert "never ENUMERATED" in why

    def test_unread_items_block_exhaustion(self) -> None:
        done, why = currently_exhausted(_rec(items_discovered=40, items_processed=10))
        assert done is False
        assert "30 of 40 item(s) still unread" in why

    def test_THE_USUAL_SHAPE_OF_A_FALSE_EXHAUSTION_CLAIM(self) -> None:
        """Every video watched, no research process extracted. Feels complete; is not."""
        done, why = currently_exhausted(_rec(items_discovered=40, items_processed=40,
                                             axes_extracted=("signal", "sizing")))
        assert done is False
        assert "the signal rules were taken and the research process was not" in why

    def test_full_coverage_is_exhausted_AS_OF_a_date(self) -> None:
        done, why = currently_exhausted(_rec(items_discovered=40, items_processed=40,
                                             axes_extracted=EXTRACTION_AXES,
                                             last_sweep="2026-08-09"))
        assert done is True
        assert "CURRENTLY_EXHAUSTED_AS_OF 2026-08-09" in why
        assert "Reopens on any new upload" in why

    def test_AN_UNDATED_SWEEP_IS_A_CLAIM_WITH_NO_EXPIRY(self) -> None:
        done, why = currently_exhausted(_rec(items_discovered=5, items_processed=5,
                                             axes_extracted=EXTRACTION_AXES))
        assert done is True
        assert "carries NO DATE" in why

    def test_unavailable_items_do_not_block_forever(self) -> None:
        done, _ = currently_exhausted(_rec(items_discovered=40, items_processed=35,
                                           unavailable_items=5,
                                           axes_extracted=EXTRACTION_AXES,
                                           last_sweep="2026-08-09"))
        assert done is True


class TestInvestigationPriority:
    def test_THERE_IS_NO_CREDIBILITY_SCORE(self) -> None:
        """Pinned deliberately: the only score is reading order, so none reads as belief."""
        exported = set(pc.__all__)
        assert not {n for n in exported if "credib" in n.lower() or "belief" in n.lower()}
        assert "investigation_priority" in exported

    def test_a_big_unverified_claim_raises_priority_not_belief(self) -> None:
        modest = investigation_priority(_rec("m", claimed_annual_return=0.2,
                                             items_discovered=10))[0]
        huge, why = investigation_priority(_rec("h", claimed_annual_return=4.0,
                                                items_discovered=10))
        assert huge > modest
        assert "It does not rank belief" in why

    def test_a_discretionary_trader_ranks_far_below_a_systematic_one(self) -> None:
        s = investigation_priority(_rec("s", systematic_status="CONFIRMED_SYSTEMATIC",
                                        items_discovered=10))[0]
        d = investigation_priority(_rec("d", systematic_status="DISCRETIONARY",
                                        items_discovered=10))[0]
        assert d < s / 10

    def test_a_marketing_claim_ranks_below_a_verified_one(self) -> None:
        v = investigation_priority(_rec("v", evidence_class="VERIFIED",
                                        items_discovered=10))[0]
        m = investigation_priority(_rec("m", evidence_class="MARKETING_CLAIM",
                                        items_discovered=10))[0]
        assert m < v

    def test_an_absurd_claim_does_not_swamp_the_ranking(self) -> None:
        """Log-magnitude: a 4000% claim measures the claimant, not the market."""
        big = investigation_priority(_rec("b", claimed_annual_return=4.0,
                                          items_discovered=10))[0]
        absurd = investigation_priority(_rec("a", claimed_annual_return=40.0,
                                             items_discovered=10))[0]
        assert absurd < big * 3


class TestSourceRoi:
    def test_an_unread_corpus_has_no_yield_and_no_evidence_of_one(self) -> None:
        roi, why = source_roi(_rec(items_discovered=50))
        assert roi is None
        assert "UNMEASURED" in why

    def test_reading_is_not_free(self) -> None:
        roi, why = source_roi(_rec(items_discovered=5, items_processed=5))
        assert roi is None
        assert "Reading is not free" in why

    def test_A_BIG_CHANNEL_WITH_NO_DESCENDANTS_IS_NOT_REWARDED_FOR_VOLUME(self) -> None:
        roi, why = source_roi(_rec(items_discovered=500, items_processed=500,
                                   acquisition_cost=0.02))
        assert roi == 0.0
        assert "volume is not a reason to keep it high in the queue" in why

    def test_a_productive_source_scores(self) -> None:
        roi, why = source_roi(_rec(items_discovered=10, items_processed=10,
                                   acquisition_cost=0.01, live_descendants=2,
                                   realized_economic_descendants=0.05))
        assert roi == pytest.approx(5.0)
        assert "2 live" in why


class TestIndependentSources:
    def test_nothing_is_unmeasured(self) -> None:
        n, why = effective_independent_sources([])
        assert n == 0.0
        assert "UNMEASURED" in why

    def test_one_source(self) -> None:
        assert effective_independent_sources([_rec("a")])[0] == 1.0

    def test_A_CITATION_CHAIN_IS_ONE_DISCOVERY(self) -> None:
        n, why = effective_independent_sources([_rec(f"p{i}") for i in range(5)])
        assert n == pytest.approx(2.0)
        assert "is one discovery" in why

    def test_genuine_convergence_counts_in_full_and_still_is_not_evidence(self) -> None:
        n, why = effective_independent_sources([_rec(f"p{i}") for i in range(3)],
                                               could_have_read_each_other=False)
        assert n == 3.0
        assert "does not substitute for this desk's own test" in why


class TestDisagreements:
    def test_an_untested_disagreement_becomes_a_conditional_question(self) -> None:
        rows = disagreement_hypotheses([Disagreement(
            topic="volatility scaling", position_a="scale to target vol", practitioner_a="A",
            position_b="never scale; it truncates the right tail", practitioner_b="B")])
        assert rows[0]["tested_here"] is False
        assert "both are right in different regimes" in str(rows[0]["why"])

    def test_a_tested_disagreement_reports_its_resolution(self) -> None:
        rows = disagreement_hypotheses([Disagreement(
            topic="x", position_a="a", practitioner_a="A", position_b="b", practitioner_b="B",
            tested_here=True, resolution="A holds in high-vol only")])
        assert "A holds in high-vol only" in str(rows[0]["why"])

    def test_a_tested_disagreement_with_no_recorded_resolution_says_so(self) -> None:
        rows = disagreement_hypotheses([Disagreement(
            topic="x", position_a="a", practitioner_a="A", position_b="b", practitioner_b="B",
            tested_here=True)])
        assert "resolution not recorded" in str(rows[0]["why"])

    def test_no_disagreements_is_an_empty_list(self) -> None:
        assert disagreement_hypotheses([]) == []


class TestSummarise:
    def test_empty_ledger_means_the_seat_has_not_run(self) -> None:
        r = summarise([])
        assert r["measured"] is False
        assert "the seat has not run" in str(r["headline"])

    def test_full_report_names_the_corpora_read_without_process(self) -> None:
        r = summarise([
            _rec("read_shallow", items_discovered=20, items_processed=20,
                 axes_extracted=("signal", "sizing"), acquisition_cost=0.01),
            _rec("never_looked"),
        ])
        assert r["measured"] is True
        assert r["practitioners"] == 2
        assert "never_looked" in r["never_enumerated"]            # type: ignore[operator]
        assert "read_shallow" in r["read_but_no_process_extracted"]   # type: ignore[operator]
        assert "the part that compounds was left behind" in str(r["headline"])

    def test_the_report_names_a_next_read(self) -> None:
        r = summarise([_rec("low", systematic_status="DISCRETIONARY", items_discovered=1),
                       _rec("high", claimed_annual_return=2.0, items_discovered=40)])
        assert r["next_read"] == "high"

    def test_disagreements_ride_along(self) -> None:
        r = summarise([_rec("a", items_discovered=1)], disagreements=[Disagreement(
            topic="t", position_a="x", practitioner_a="A", position_b="y", practitioner_b="B")])
        assert r["untested_disagreements"] == 1
