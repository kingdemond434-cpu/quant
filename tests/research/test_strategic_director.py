"""RANK 3 strategic director. The contract IS the product, so these are its teeth.

An LLM asked for strategy returns fluent, plausible, unfalsifiable advice, and fluent advice is
worse than none because it FEELS like progress and cannot be checked. Two properties matter most:
  * a recommendation missing bottleneck / impact / opportunity-cost / success-metric is REJECTED;
  * "find unused capability before inventing new capability" is enforced on a DECLARED field, so
    the model cannot dodge it by rewording -- a rule that lives only in a prompt is advisory.
"""

from __future__ import annotations

import json

from libs.research.strategic_director import (
    DOSSIER_SOURCES,
    KIND_ACTIVATE,
    KIND_BUILD,
    MIN_FIELD_CHARS,
    REQUIRED_FIELDS,
    Dossier,
    Recommendation,
    assemble_dossier,
    build_prompt,
    director_report,
    parse_recommendations,
    rank,
    to_ledger_commands,
)

_GOOD = {
    "title": "Wire libs/execution/algos.py into the ExecutionEngine",
    "kind": "activate",
    "bottleneck": "TWAP/POV schedules exist but ExecutionEngine never calls them; child-order "
                  "slicing is unavailable on every parent order today",
    "expected_impact": "parent orders above venue min-notional get sliced, cutting expected "
                       "impact cost on the carry sleeve",
    "opportunity_cost": "one cycle not spent on the data registry backfill work",
    "success_metric": "realised slippage bps on sliced parents vs unsliced baseline over 20 fills",
}


def _dossier(dormant: int = 171) -> Dossier:
    return Dossier(present={"dormancy": {}}, missing=[], dormant_count=dormant)


def _rec(**over: object) -> dict:
    d = dict(_GOOD)
    d.update(over)
    return d


class TestTheContractRejectsFluentAdvice:
    def test_a_well_formed_recommendation_is_accepted(self) -> None:
        res = parse_recommendations(json.dumps([_GOOD]), _dossier())
        assert len(res.accepted) == 1 and not res.rejected
        assert res.accepted[0].kind == KIND_ACTIVATE

    def test_each_required_field_is_individually_load_bearing(self) -> None:
        for f in REQUIRED_FIELDS:
            res = parse_recommendations(json.dumps([_rec(**{f: None})]), _dossier())
            assert not res.accepted, f"a recommendation with no {f} must be rejected"
            assert f in res.rejected[0].reason

    def test_boilerplate_is_rejected_not_just_absence(self) -> None:
        """'Improves things' is present, short, and says nothing -- the actual failure mode."""
        res = parse_recommendations(json.dumps([_rec(bottleneck="improves throughput")]),
                                    _dossier())
        assert not res.accepted
        assert "boilerplate" in res.rejected[0].reason

    def test_the_threshold_is_a_real_content_bar(self) -> None:
        assert MIN_FIELD_CHARS > 15, "'improves things' is 15 chars and must not pass"

    def test_prose_instead_of_json_is_rejected_loudly(self) -> None:
        res = parse_recommendations("I recommend improving the validation stack.", _dossier())
        assert not res.accepted and res.rejected
        assert "no JSON array" in res.rejected[0].reason

    def test_broken_json_is_reported_not_swallowed(self) -> None:
        # brackets present but the contents are malformed -- distinct from the no-array case above,
        # and both must reject rather than yield a partial list
        res = parse_recommendations('[{"title": "x", "kind":}]', _dossier())
        assert not res.accepted and "unparseable" in res.rejected[0].reason

    def test_a_truncated_response_is_rejected(self) -> None:
        """A response cut off mid-stream has an opening bracket and no close."""
        res = parse_recommendations('[{"title": "x",', _dossier())
        assert not res.accepted and res.rejected

    def test_a_fenced_response_still_parses(self) -> None:
        fenced = "Here you go:\n```json\n" + json.dumps([_GOOD]) + "\n```\nHope that helps."
        assert len(parse_recommendations(fenced, _dossier()).accepted) == 1

    def test_an_unknown_kind_is_rejected(self) -> None:
        res = parse_recommendations(json.dumps([_rec(kind="ponder")]), _dossier())
        assert not res.accepted and "not one of" in res.rejected[0].reason

    def test_every_rejection_carries_a_reason(self) -> None:
        res = parse_recommendations(json.dumps([_rec(kind="nope"), _rec(bottleneck="x")]),
                                    _dossier())
        assert len(res.rejected) == 2
        assert all(len(r.reason) > 30 for r in res.rejected)

    def test_nothing_is_silently_dropped(self) -> None:
        res = parse_recommendations(json.dumps([_GOOD, _rec(kind="bad"), "not an object"]),
                                    _dossier())
        assert res.n_seen == 3, "a director whose bad output vanishes looks like one that ran fine"


class TestThePriorityRuleIsEnforcedNotRequested:
    """A rule that lives only in the prompt is advisory; the model can and will ignore it."""

    def test_build_is_rejected_while_capabilities_sit_dormant(self) -> None:
        res = parse_recommendations(json.dumps([_rec(kind=KIND_BUILD)]), _dossier(dormant=171))
        assert not res.accepted
        assert "before inventing new capability" in res.rejected[0].reason.lower()

    def test_build_is_allowed_with_an_explicit_justification(self) -> None:
        rec = _rec(kind=KIND_BUILD,
                   why_not_activation="no existing module ingests options surfaces; the three "
                                      "dormant candidates all operate on spot bars only")
        assert len(parse_recommendations(json.dumps([rec]), _dossier(171)).accepted) == 1

    def test_a_token_justification_does_not_satisfy_it(self) -> None:
        rec = _rec(kind=KIND_BUILD, why_not_activation="nothing fits")
        assert not parse_recommendations(json.dumps([rec]), _dossier(171)).accepted

    def test_the_rule_does_not_bite_when_nothing_is_dormant(self) -> None:
        """It is a priority rule, not a ban on ever building anything again."""
        res = parse_recommendations(json.dumps([_rec(kind=KIND_BUILD)]), _dossier(dormant=0))
        assert len(res.accepted) == 1

    def test_activation_kinds_are_never_blocked_by_it(self) -> None:
        for kind in ("activate", "merge", "retire", "unlock"):
            res = parse_recommendations(json.dumps([_rec(kind=kind)]), _dossier(171))
            assert len(res.accepted) == 1, f"{kind} must pass -- it IS the preferred direction"

    def test_the_prompt_states_the_rule_and_the_measured_count(self) -> None:
        p = build_prompt(_dossier(171))
        assert "171" in p and "BEFORE INVENTING NEW" in p.upper()

    def test_ranking_puts_activation_above_building_at_equal_roi(self) -> None:
        build = Recommendation("b", KIND_BUILD, "x", "y", "z", "w", "just because", 100.0)
        act = Recommendation("a", KIND_ACTIVATE, "x", "y", "z", "w", "", 100.0)
        assert [r.kind for r in rank([build, act])] == [KIND_ACTIVATE, KIND_BUILD]


class TestTheDossierIsHonestAboutHoles:
    def test_missing_artifacts_are_named_not_skipped(self, tmp_path) -> None:
        d = assemble_dossier(tmp_path)
        assert d.missing and not d.complete
        # derived, not a literal: adding a dossier source must not silently shrink this assertion
        assert len(d.missing) == len(DOSSIER_SOURCES), "every declared source must be accounted for"

    def test_it_reads_the_real_repo_without_crashing(self) -> None:
        d = assemble_dossier()
        assert isinstance(d.dormant_count, int)
        assert d.present or d.missing

    def test_the_dormant_count_is_extracted_from_the_cycle_artifact(self, tmp_path) -> None:
        (tmp_path / "web").mkdir()
        (tmp_path / "web/intelligence_cycle.json").write_text(json.dumps({
            "capabilities": [{"capability": "dormancy_hunter",
                              "report": {"counts": {"module": 101, "script": 57}}}]}), "utf-8")
        assert assemble_dossier(tmp_path).dormant_count == 158

    def test_the_prompt_discloses_what_was_missing(self) -> None:
        d = Dossier(present={}, missing=["moat_audit (data/moat_quality.json)"], dormant_count=3)
        assert "moat_audit" in build_prompt(d), (
            "a director reasoning off a dossier with invisible holes is GAP #77 again")


class TestLedgerRouting:
    """Routing through the ledger is what makes this a role rather than a report."""

    def test_each_accepted_recommendation_becomes_an_add_command(self) -> None:
        res = parse_recommendations(json.dumps([_GOOD]), _dossier())
        cmds = to_ledger_commands(res)
        assert len(cmds) == 1 and cmds[0][0] == "add"
        assert "--source" in cmds[0] and "--summary" in cmds[0]

    def test_the_summary_carries_all_four_judgeable_fields(self) -> None:
        cmd = to_ledger_commands(parse_recommendations(json.dumps([_GOOD]), _dossier()))[0]
        summary = cmd[cmd.index("--summary") + 1]
        for marker in ("BOTTLENECK:", "IMPACT:", "COST:", "SUCCESS:"):
            assert marker in summary

    def test_rejected_recommendations_are_never_ledgered(self) -> None:
        res = parse_recommendations(json.dumps([_rec(kind="bogus")]), _dossier())
        assert to_ledger_commands(res) == []

    def test_roi_is_passed_through_when_given(self) -> None:
        cmd = to_ledger_commands(parse_recommendations(
            json.dumps([_rec(roi_bps=42.0)]), _dossier()))[0]
        assert "--roi-bps" in cmd and "42.0" in cmd

    def test_the_report_is_json_serialisable(self) -> None:
        d = _dossier()
        json.dumps(director_report(parse_recommendations(json.dumps([_GOOD]), d), d))


class TestActivationReadiness:
    """Everything except the network call must work today, or 'ready' is a claim not a fact."""

    def test_the_prompt_builds_with_no_credit_and_no_dossier(self, tmp_path) -> None:
        assert len(build_prompt(assemble_dossier(tmp_path))) > 500

    def test_an_empty_array_is_a_clean_zero_not_an_error(self) -> None:
        res = parse_recommendations("[]", _dossier())
        assert res.accepted == [] and res.rejected == []

    def test_the_contract_is_published_in_the_report(self) -> None:
        d = _dossier()
        rep = director_report(parse_recommendations("[]", d), d)
        assert rep["contract"]["required_fields"] == list(REQUIRED_FIELDS)
