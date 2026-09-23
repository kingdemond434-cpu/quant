"""The frontier miner: unverified claims are welcome, and almost everything is refused.

Those two sentences look contradictory and are the whole design. The principal's instruction is
that ALL information -- verified or not, ex-employee, anonymous, translated forum -- is admitted
and reverse-engineered, because the desk's own governance says research is anti-timid and
"unverified public claims are welcome as hypotheses and are never privileged by their source".
The mandate's instruction is equally strong in the other direction: a frontier miner that cannot
refuse will bury the desk in sophisticated modules that measurably do nothing.

Both hold because they act at different places. ADMISSION is wide open: a Grade-D forum claim
enters the queue and gets scored. THE VERDICT is narrow: it comes from our own replication, the
ten gates and measured rent, and no grade at any weight touches it. What the grade orders is
ATTENTION, because attention is finite.

What these tests pin, in order of how expensive the mistake would be:

  THE LEGAL BOUNDARY   publicly given versus taken. Nothing solicited, leaked or confidential is
                       readable at any expected dE[log W], and the refusals are by name.
  THE REFUSALS         a vanity-scale capability, a buzzword, and a capability that needs more
                       capital than the desk has must all score below the queue threshold.
  THE UNKNOWN LANES    a registry only finds what its author already listed, so the unknown-firm,
                       unknown-capability and unaddressed-capability lanes must actually produce.
  THE LADDER           nothing reaches PROVEN without being MEASURED, including the miner's own
                       imports.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

fi_ont = pytest.importorskip("frontier_intel.ontology")
fi_reg = pytest.importorskip("frontier_intel.registry")
fi_roi = pytest.importorskip("frontier_intel.roi")
fi_q = pytest.importorskip("frontier_intel.queue")
fi_unk = pytest.importorskip("frontier_intel.unknowns")


# ------------------------------------------------------------------- the boundary that never moves

class TestPubliclyGivenVersusTaken:
    @pytest.mark.parametrize("kind", ["ex_employee_public", "anonymous_claim", "translated_forum",
                                      "public_forum", "public_video", "community_wiki"])
    def test_unverified_public_claims_are_readable(self, kind: str) -> None:
        """ADMITTED ON PURPOSE. An ex-employee describing publicly how a shop schedules its
        experiments is a hypothesis; refusing it would be timidity wearing rigour's clothes."""
        ok, why = fi_reg.admissible(kind)
        assert ok, why

    @pytest.mark.parametrize("kind", ["solicited_mnpi", "solicited_confidential",
                                      "employee_confidential", "leaked_dataset",
                                      "proprietary_source", "paywalled_bypass"])
    def test_taken_information_is_refused_whatever_it_might_be_worth(self, kind: str) -> None:
        """THE LINE IS NOT VERIFIED VS UNVERIFIED -- it is publicly GIVEN vs TAKEN. No expected
        dE[log W] makes the second a research method."""
        ok, why = fi_reg.admissible(kind)
        assert not ok and why

    def test_an_unrecognised_source_class_is_refused_rather_than_graded_low(self) -> None:
        """An admissibility list, not a preference list: the alternative is deciding legality per
        article, which is the same as not deciding it."""
        ok, why = fi_reg.admissible("something_new")
        assert not ok and "ADMISSIBILITY" in why

    def test_the_two_ex_employee_classes_are_distinguished(self) -> None:
        """`ex_employee_public` and `employee_confidential` differ by who initiated it and what
        was owed -- and the refusal says so, because a reader who cannot tell them apart will
        collapse them in one direction or the other."""
        assert fi_reg.admissible("ex_employee_public")[0] is True
        why = fi_reg.admissible("employee_confidential")[1]
        assert "PUBLICLY" in why or "publicly" in why


class TestGradeOrdersAttentionNeverTruth:
    def test_grade_d_can_raise_priority(self) -> None:
        """It could not, first draft, and that was the desk's timidity defect in a new costume."""
        assert fi_reg.may_prioritise("D") is True
        assert fi_reg.grade_weight("D") > 0.0

    def test_but_a_paper_still_outranks_a_rumour_for_attention(self) -> None:
        assert fi_reg.grade_weight("A") > fi_reg.grade_weight("D")

    def test_firm_standing_is_a_prior_and_says_when_it_is_not_measured(self) -> None:
        w, why = fi_reg.investigation_weight("High-Flyer", "A")
        assert w > 0 and ("prior" in why or "MEASURED" in why)

    def test_an_unknown_firm_still_gets_a_weight_rather_than_a_crash(self) -> None:
        w, _ = fi_reg.investigation_weight("Some Shop Nobody Listed", "D")
        assert 0.0 <= w <= 1.0


# ------------------------------------------------------------------------ the refusals that matter

def _c(**kw):
    base = dict(frontier_id="F", firm="f", capability="DATA", evidence_grade="A", gap="MISSING",
                p_success=0.5, breadth=1.0, persistence_years=1.0, novelty=0.5,
                costs={"engineering": 10.0, "compute": 1.0, "data": 1.0,
                       "complexity": 1.0, "operational_risk": 1.0})
    base.update(kw)
    return fi_roi.Candidate(**base)


class TestItRefusesMoreThanItQueues:
    def test_a_capability_needing_more_capital_than_the_desk_has_is_worthless_here(self) -> None:
        """§48: do not conclude 'we need 10,000 GPUs'. Replicate the FUNCTION, not the scale."""
        fit, why = fi_roi.capital_fit(_c(capacity_floor_usd=5_000_000))
        assert fit == 0.0 and "not for us at any priority" in why

    def test_a_tiny_capacity_capability_is_worth_MORE_here_than_at_the_firm(self) -> None:
        """The desk's actual structural advantage, and a scorer blind to it would systematically
        prefer the things this desk is worst placed to exploit."""
        fit, why = fi_roi.capital_fit(_c(capacity_floor_usd=100.0))
        assert fit > 1.0 and "structural advantage" in why

    def test_a_buzzword_with_no_estimated_gain_scores_zero(self) -> None:
        out = fi_roi.priority(_c(expected_delta_elog=None, intermediate="", p_success=0.9))
        assert out["verdict"] == "REFUSE" and "not been valued" in out["why"] + out["value_why"]

    def test_a_candidate_with_no_estimated_cost_is_refused_not_ranked_first(self) -> None:
        """An unstated cost scores infinitely well, which is how a queue fills with unbounded
        projects."""
        out = fi_roi.priority(_c(expected_delta_elog=1.0, costs={}))
        assert out["verdict"] == "REFUSE" and "cost is unstated" in out["why"]

    def test_complexity_and_operational_risk_are_in_the_denominator(self) -> None:
        """Charged BEFORE priority, not after measurement -- after measurement the code is in."""
        cheap = fi_roi.priority(_c(expected_delta_elog=1e-4))
        heavy = fi_roi.priority(_c(expected_delta_elog=1e-4,
                                   costs={"engineering": 10.0, "compute": 1.0, "data": 1.0,
                                          "complexity": 50.0, "operational_risk": 30.0}))
        assert heavy["priority"] < cheap["priority"]
        assert heavy["complexity_rent"] > cheap["complexity_rent"]

    def test_a_refusal_is_kept_with_its_reason_rather_than_ranked_last(self) -> None:
        """A refused candidate must not come back the next time the queue looks short."""
        out = fi_roi.rank([_c(expected_delta_elog=1e-12)])
        assert out["n_queued"] == 0 and out["n_refused"] == 1
        assert out["refused"][0]["why"]


class TestValueIsHonestAboutItsUnits:
    def test_an_unmeasurable_gain_may_still_queue_on_a_named_intermediate(self) -> None:
        """Without this the ranking only ever funds what is already measurable, which is a system
        that cannot learn anything new."""
        out = fi_roi.priority(_c(expected_delta_elog=None, intermediate="research_velocity",
                                 intermediate_value=0.5, p_success=0.8, breadth=3.0,
                                 persistence_years=5.0, novelty=0.9))
        assert out["verdict"] == "QUEUE" and "UNMEASURED" in out["basis"]

    def test_an_unnamed_intermediate_is_not_a_free_pass(self) -> None:
        out = fi_roi.priority(_c(expected_delta_elog=None, intermediate="vibes",
                                 intermediate_value=99.0))
        assert out["verdict"] == "REFUSE"

    def test_the_basis_travels_with_the_number(self) -> None:
        """A caller that sums a research-velocity score and a dE[log W] has made a category
        error, and the string is what makes that visible."""
        direct = fi_roi.priority(_c(expected_delta_elog=1e-4))
        indirect = fi_roi.priority(_c(expected_delta_elog=None, intermediate="breadth_gain",
                                      intermediate_value=1.0))
        assert direct["basis"] == "dE[log W]/day"
        assert "UNMEASURED" in indirect["basis"]


# ------------------------------------------------------------------------ the unknown-unknown lanes

class TestTheRegistryIsNotTheLimit:
    def test_an_unlisted_firm_named_repeatedly_becomes_a_candidate(self) -> None:
        """A registry only finds what its author already knew to list, so this lane is what stops
        the miner converging on confirming what it already believed."""
        found = fi_unk.unknown_firms([
            "Shanghai Qingyuan Capital scaled its research cluster alongside High-Flyer",
            "Qingyuan Capital is hiring for distributed training",
        ])
        names = {u.name for u in found}
        assert any("Qingyuan" in n for n in names), names

    def test_a_tracked_firm_written_differently_is_not_reported_as_unknown(self) -> None:
        assert not [u for u in fi_unk.unknown_firms(
            ["Man AHL Capital published", "Man AHL Capital again"]) if "AHL" in u.name]

    def test_capabilities_no_module_owns_are_named_without_crawling_anything(self) -> None:
        """A fact about our own tree: 'no module addresses MARKET_IMPACT' is a measurement, and
        the kind of gap that stays open for years because nothing names it out loud."""
        rows = fi_unk.unaddressed_capabilities()
        assert rows, "the ontology claims every capability has an owner, which would be a first"
        assert all(r.kind == "UNADDRESSED" and r.why for r in rows)

    def test_a_finding_that_maps_to_no_capability_is_kept_not_forced(self) -> None:
        """`map_to_capabilities` refuses to fuzzy-match on purpose: a mapper that assigns
        SOMETHING to every article always finds a gap."""
        assert fi_ont.map_to_capabilities("a general article about markets") == ()
        rows = fi_unk.unknown_capabilities([{"frontier_id": "x", "public_observation": "vague"}])
        assert rows and rows[0].kind == "CAPABILITY"

    def test_the_exploration_budget_is_reserved_rather_than_earned(self) -> None:
        """The score of an unknown is computed by a model that does not know about it, so a
        purely scored queue spends zero here."""
        s = fi_unk.survey(texts=[], findings=[])
        assert 0.05 <= s["exploration_fraction"] <= 0.15
        assert "converges on confirming" in s["why_reserved"]


# ------------------------------------------------------------------------------- the import ladder

class TestNothingIsBelievedBecauseItWasBuiltWell:
    def test_a_candidate_cannot_jump_to_proven(self, tmp_path) -> None:
        ok, why = fi_q.can_transition("IMPLEMENTING", "PROVEN")
        assert not ok and "MEASURED" in why

    def test_the_legal_path_runs_through_measuring(self) -> None:
        state = "DISCOVERED"
        for nxt in ("EXTRACTED", "DEDUPED", "GAP_CONFIRMED", "PRIORITIZED", "IMPLEMENTING",
                    "TESTING", "CHALLENGER", "MEASURING", "PROVEN"):
            ok, why = fi_q.can_transition(state, nxt)
            assert ok, f"{state} -> {nxt}: {why}"
            state = nxt

    def test_killing_is_legal_from_anywhere(self) -> None:
        """A ladder that made it hard to kill things would fill up."""
        for s in fi_q.STATES:
            assert fi_q.can_transition(s, "GRAVEYARD")[0]

    def test_the_same_finding_read_twice_is_one_candidate(self, tmp_path) -> None:
        p = tmp_path / "q.jsonl"
        kw = dict(firm="X", capability="DATA", source_url="http://a?utm=1",
                  claim="they use many sources", evidence_grade="C", source_kind="public_forum")
        fi_q.discover(**kw, path=p)
        again = fi_q.discover(**kw, path=p)
        assert again.get("already_known") is True
        assert fi_q.summary(p)["candidates"] == 1

    def test_an_illegal_transition_is_recorded_rather_than_silently_dropped(self, tmp_path) -> None:
        """An implementer repeatedly trying to jump a card to PROVEN is a defect in the
        implementer, and a version that returned False would hide it."""
        p = tmp_path / "q.jsonl"
        row = fi_q.discover(firm="X", capability="DATA", source_url="u", claim="c",
                            evidence_grade="A", source_kind="official_blog", path=p)
        fi_q.advance(row["candidate_id"], "PROVEN", path=p)
        assert any(r.get("refused_transition") == "PROVEN" for r in fi_q.rows(p))

    def test_graveyard_is_not_deletion(self, tmp_path) -> None:
        p = tmp_path / "q.jsonl"
        row = fi_q.discover(firm="X", capability="DATA", source_url="u", claim="c",
                            evidence_grade="A", source_kind="official_blog", path=p)
        fi_q.advance(row["candidate_id"], "GRAVEYARD", why="did not transfer", path=p)
        assert fi_q.summary(p)["candidates"] == 1
        assert fi_q.current(p)[row["candidate_id"]]["state"] == "GRAVEYARD"


# -------------------------------------------------------------------------------- the wiring itself

class TestItIsAnOrganNotAFile:
    def test_every_capability_names_its_allocator_level(self) -> None:
        """A finding with no level is a finding with no price: the level decides which budget pays
        for it and which ledger measures it."""
        for c in fi_ont.CAPABILITIES:
            assert c.level in fi_ont.LEVELS, c.name

    def test_the_frontier_level_exists_in_the_allocator_stack(self) -> None:
        """The seventh allocator, and the integration point: this organ's output is spent by the
        six below it in their own currencies."""
        from libs.ops import allocators as al
        assert "frontier" in al.BY_NAME
        assert al.BY_NAME["frontier"].level == 0
        assert al.BY_NAME["frontier"].feeds == ("information",)

    def test_the_supervisor_declares_that_it_does_not_merge(self) -> None:
        """A safety boundary, stated in the artifact rather than only in a docstring: an
        implementer that can both propose and merge into the tree that sizes real positions is one
        bad extraction from a live defect."""
        sup = pytest.importorskip("frontier_intel.frontier_supervisor")
        doc = sup.one_pass(fetch=False)
        assert "does not write code" in doc["boundary"]
        assert doc["rent"]["status"] == "UNMEASURED"

    def test_a_pass_with_no_new_finding_still_produces_the_standing_gaps(self) -> None:
        """NEVER IDLE. An hour with no novelty is not an hour with nothing to do, and a supervisor
        that returned early would do most of its nothing during the quiet weeks."""
        sup = pytest.importorskip("frontier_intel.frontier_supervisor")
        doc = sup.one_pass(fetch=False)
        assert doc["rows_scouted"] == 0
        assert doc["capability_matrix_missing"] > 0
        assert doc["ranked"]["n_queued"] > 0, "a quiet pass produced no work at all"
