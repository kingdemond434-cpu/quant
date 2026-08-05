"""THE PANEL'S FENCE AND ITS AGGREGATION -- the two places a panel silently goes wrong.

A panel asked "how do we get survivors" has one overwhelmingly easy answer available: LOWER THE
BAR. It creates survivors by arithmetic alone, it sounds like methodology, and every model will
find it. So the fence is the safety-critical part of this organ and it is tested first -- both
directions, because a fence that refuses everything is as useless as one that refuses nothing.

TWO HOLES WERE FOUND BY THESE TESTS BEFORE THE ORGAN EVER RAN, and both would have put a
gate-loosening proposal onto a ranked action list under a heading saying the desk is hunting
survivors:
  * "relax the MULTIPLICITY CORRECTION so more cells pass" -- `multiplicity` and `correction`
    were missing from the loosening pattern entirely;
  * "drop the UNDERPERFORMING strategies" -- the pattern anchored on \\bunderperform\\b, so the
    -ing form, which is how anyone would actually write it, sailed through.

The second axis is aggregation. Agreement across seats is the panel's only real signal, and it is
only worth anything because round two FORCES each seat to refute the others first. Merging must
therefore be conservative: over-merging invents consensus, under-merging hides it.
"""
from __future__ import annotations

import json
from pathlib import Path

from libs.research.survivor_panel import (
    BOTTLENECK_CLASSES,
    FORBIDDEN,
    Proposal,
    build_dossier,
    cross_examination_prompt,
    forbidden_direction,
    parse_proposals,
    rank_proposals,
    round_one_prompt,
)


class TestTheFenceRefusesTheEasyAnswer:
    def test_loosening_a_gate_is_refused_in_every_spelling(self) -> None:
        for text in ("Lower the significance threshold to 0.10",
                     "Relax the multiplicity correction so more cells pass",
                     "Soften the Holm correction across the cohort",
                     "Widen the deflated Sharpe hurdle to admit more candidates",
                     "Reduce alpha stringency to increase throughput",
                     "Ease the p-value criterion for stage A"):
            assert forbidden_direction(text), f"NOT REFUSED: {text}"

    def test_post_hoc_selection_is_refused(self) -> None:
        """Survivorship by another name -- it produces a backtest that cannot be wrong."""
        for text in ("Drop the underperforming strategies and re-run the campaign",
                     "Prune the worst-performing cells before scoring",
                     "Exclude the losing candidates from the multiplicity count"):
            assert forbidden_direction(text), f"NOT REFUSED: {text}"

    def test_size_leverage_and_the_deadman_switch_are_refused(self) -> None:
        assert forbidden_direction("Increase leverage to 3x on the surviving sleeve")
        assert forbidden_direction("Scale up position size once a clock is green")
        assert forbidden_direction("Adjust run_deadman_switch to allow the campaign through")

    def test_removing_a_validation_stage_is_refused(self) -> None:
        assert forbidden_direction("Skip the forward validation to move faster")
        assert forbidden_direction("Disable out-of-sample testing for microstructure cells")

    def test_the_legitimate_answers_are_NOT_refused(self) -> None:
        """A fence that refuses everything is a fence nobody can use. These are exactly the
        actions the desk's own power model recommends, and every one must pass."""
        for text in ("Extend the sub-daily price lake to the newly listed assets",
                     "Pool correlated cells to raise the effective sample length",
                     "Record more L2 tape so T grows past the detection floor",
                     "Reduce the number of hypotheses generated per campaign by design",
                     "Screen at second-scale horizons where the moat resolves fastest",
                     "Collect the unlock calendar as dated release rows"):
            assert not forbidden_direction(text), f"WRONGLY REFUSED: {text}"

    def test_reducing_hypotheses_by_design_differs_from_dropping_losers(self) -> None:
        """The distinction the whole fence turns on. Choosing a narrower campaign BEFORE seeing
        results is good design; discarding candidates AFTER seeing them is survivorship."""
        assert not forbidden_direction("Pre-register fewer hypotheses per campaign")
        assert forbidden_direction("Drop the failed hypotheses then recompute the correction")

    def test_every_forbidden_entry_carries_a_reason(self) -> None:
        for pattern, why in FORBIDDEN:
            assert pattern and len(why) > 30, f"{pattern} has no usable reason"


class TestTheDossierIsMadeOfArtifactsNotProse:
    def test_a_missing_artifact_is_named_never_silently_omitted(self, tmp_path: Path) -> None:
        """A seat reasoning about a gap it cannot see gives advice about a desk that does not
        exist. Absence must be visible IN the dossier."""
        d = build_dossier(tmp_path)
        assert d["missing_artifacts"], "an empty checkout must report every artifact missing"
        assert "data/type2_cost.json" in d["missing_artifacts"]

    def test_every_figure_carries_its_source_path(self, tmp_path: Path) -> None:
        d = build_dossier(tmp_path)
        for block in ("type2", "forward_slots", "moat"):
            assert d[block]["source"].endswith(".json"), f"{block} cites no source"

    def test_the_dossier_states_the_constraints_on_answers(self, tmp_path: Path) -> None:
        d = build_dossier(tmp_path)
        joined = " ".join(d["constraints_on_answers"]).lower()
        assert "threshold" in joined and "leverage" in joined
        assert any("post" in c.lower() or "after seeing" in c.lower()
                   for c in d["constraints_on_answers"])

    def test_the_prompts_carry_the_numbers_and_the_rules(self, tmp_path: Path) -> None:
        d = build_dossier(tmp_path)
        system, user = round_one_prompt(d)
        assert "never propose loosening" in system.lower()
        assert "STRICT JSON" in system
        for cls, _ in BOTTLENECK_CLASSES:
            assert cls in user, f"{cls} is not offered to the seat"

    def test_cross_examination_demands_refutation_not_summary(self, tmp_path: Path) -> None:
        """One round is not a panel. If round two stops demanding a refutation, agreement across
        seats stops being evidence and becomes a shared prior."""
        system, user = cross_examination_prompt(build_dossier(tmp_path),
                                                [("s1", "A"), ("s2", "B")])
        assert "refute" in system.lower()
        assert "do not summarise" in system.lower()
        assert "SEAT A" in user and "SEAT B" in user

    def test_other_seats_are_anonymised_in_cross_examination(self, tmp_path: Path) -> None:
        """A seat told WHICH model wrote an answer rates the brand as much as the argument."""
        _s, user = cross_examination_prompt(build_dossier(tmp_path),
                                            [("openai-flagship", "claim x")])
        assert "openai-flagship" not in user


class TestParsingAndAggregation:
    def test_a_fenced_json_response_parses(self) -> None:
        body = ('```json\n{"primary_bottleneck": "SAMPLE_LENGTH", "confidence": 0.7, '
                '"why": "T is short", "proposals": [{"action": "Record more tape", '
                '"bottleneck": "SAMPLE_LENGTH", "rationale": "T is the lever", '
                '"testable_in_days": 30}]}\n```')
        props, doc = parse_proposals("s1", body)
        assert doc["parse"] == "OK" and doc["primary_bottleneck"] == "SAMPLE_LENGTH"
        assert [p.action for p in props] == ["Record more tape"]

    def test_an_unparseable_response_is_recorded_never_dropped(self) -> None:
        """'The seat replied and we could not read it' and 'the seat said nothing' are different
        facts; collapsing them shrinks the panel to whichever models format well."""
        props, doc = parse_proposals("s1", "I think the issue is overfitting, broadly speaking.")
        assert props == []
        assert doc["parse"] == "FAILED" and doc["raw_head"]

    def test_a_refused_proposal_is_parsed_and_flagged_not_discarded(self) -> None:
        body = json.dumps({"proposals": [
            {"action": "Lower the significance threshold", "rationale": "more throughput"}]})
        props, _ = parse_proposals("s1", body)
        assert len(props) == 1 and props[0].refused, (
            "a refused proposal must survive parsing -- that a seat proposed it is information")

    def test_refused_proposals_never_reach_the_ranking(self) -> None:
        ranked = rank_proposals([
            Proposal("s1", "Lower the significance threshold", refused="loosens a gate"),
            Proposal("s2", "Record more L2 tape for sample length"),
        ])
        assert [p.action for p in ranked] == ["Record more L2 tape for sample length"]

    def test_the_same_action_from_two_seats_merges_and_outranks(self) -> None:
        """Agreement is the signal, and only because round two forced disagreement first."""
        ranked = rank_proposals([
            Proposal("s1", "Extend the sub-daily price lake to newly listed assets",
                     testable_in_days=60),
            Proposal("s2", "Extend the sub-daily lake to the newly listed assets it names",
                     testable_in_days=45),
            Proposal("s3", "Rebuild the cost model from venue fee schedules", testable_in_days=10),
        ])
        assert ranked[0].n_agreeing_seats if hasattr(ranked[0], "n_agreeing_seats") \
            else len(set(ranked[0].agreed_by)) == 2
        assert len(set(ranked[0].agreed_by)) == 2
        assert ranked[0].testable_in_days == 45, "the merged entry keeps the FASTEST estimate"

    def test_distinct_actions_do_not_merge_into_invented_consensus(self) -> None:
        ranked = rank_proposals([
            Proposal("s1", "Record more L2 tape to grow sample length"),
            Proposal("s2", "Rebuild the execution cost model from venue fee schedules"),
        ])
        assert len(ranked) == 2
        assert all(len(set(p.agreed_by)) == 1 for p in ranked)

    def test_speed_breaks_ties_among_equally_agreed_proposals(self) -> None:
        ranked = rank_proposals([Proposal("s1", "Alpha action here", testable_in_days=200),
                                 Proposal("s2", "Beta action there", testable_in_days=20)])
        assert ranked[0].action == "Beta action there"

    def test_a_proposal_with_no_estimate_sorts_behind_one_with_a_fast_estimate(self) -> None:
        ranked = rank_proposals([Proposal("s1", "Unknown timing action"),
                                 Proposal("s2", "Known fast action", testable_in_days=15)])
        assert ranked[0].action == "Known fast action"
