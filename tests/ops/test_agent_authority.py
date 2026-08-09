"""AGENT AUTHORITY TESTS — the refusals are the product.

A permission module is only worth having if the refusals hold under the arguments that will
actually be made. Two of those arguments are made constantly and both are wrong:

    "the model is much better now"        -> capability is not authority
    "it only needs one more level"        -> a skipped rung is an ungoverned one

and one is never made out loud but is what configuration drift does by itself: a component ends up
on a capital-sensitive rung without the principal ever granting it. All three are pinned below.
"""

from __future__ import annotations

import pytest

from libs.ops.agent_authority import (
    CAPITAL_SENSITIVE,
    LEVELS,
    AgentGrant,
    BlastRadius,
    escalate,
    least_privilege_gap,
    level_index,
    permitted,
    summarise,
)


class TestLadder:
    def test_unknown_level_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown authority level"):
            level_index("L9_GOD_MODE")

    def test_the_ladder_is_ordered(self) -> None:
        assert [level_index(x) for x in LEVELS] == list(range(len(LEVELS)))

    def test_only_the_top_two_rungs_move_money(self) -> None:
        assert set(CAPITAL_SENSITIVE) == {"L5_LIMITED_EXECUTION", "L6_NORMAL_EXECUTION"}

    def test_an_unknown_level_on_the_grant_is_refused_at_construction(self) -> None:
        with pytest.raises(ValueError, match="unknown authority level"):
            AgentGrant(agent_id="x", level="L7_WHATEVER")


class TestBlastRadius:
    def test_UNASSESSED_IS_NOT_SAFE(self) -> None:
        assert BlastRadius().severity == "UNMEASURED"

    def test_ZERO_IS_AN_ANSWER_AND_SILENCE_IS_NOT(self) -> None:
        """A read-only hunter really does have zero financial blast radius.

        Inferring UNMEASURED from a zero would flag the safest component on the desk as the least
        known, which trains a reader to ignore the field entirely.
        """
        assert BlastRadius(assessed=True, financial=0.0).severity == "NONE"
        assert BlastRadius(assessed=False, financial=0.0).severity == "UNMEASURED"

    def test_propagation_is_unbounded_however_small_the_money(self) -> None:
        b = BlastRadius(assessed=True, financial=0.0001, propagation=True)
        assert b.severity == "UNBOUNDED"

    def test_irrecoverable_data_is_unbounded(self) -> None:
        assert BlastRadius(assessed=True, financial=0.0001,
                           irrecoverable_data=True).severity == "UNBOUNDED"

    def test_an_unassessed_component_is_not_promoted_to_unbounded(self) -> None:
        """UNMEASURED outranks every other label: we do not know it propagates, we know nothing."""
        assert BlastRadius(propagation=True).severity == "UNMEASURED"

    @pytest.mark.parametrize(("fin", "sev"), [(0.5, "SEVERE"), (0.05, "MATERIAL"),
                                              (0.001, "CONTAINED")])
    def test_financial_bands(self, fin: float, sev: str) -> None:
        assert BlastRadius(assessed=True, financial=fin).severity == sev


class TestPermitted:
    def test_within_grant(self) -> None:
        g = AgentGrant(agent_id="researcher", level="L2_RESEARCH_COMPUTE")
        ok, why = permitted(g, "L1_PRIVATE_READ")
        assert ok is True
        assert "within" in why

    def test_above_grant_is_refused(self) -> None:
        g = AgentGrant(agent_id="hunter", level="L0_PUBLIC_READ")
        ok, why = permitted(g, "L2_RESEARCH_COMPUTE")
        assert ok is False
        assert "REFUSED" in why

    def test_CONFIGURATION_CANNOT_REACH_A_CAPITAL_RUNG(self) -> None:
        """Even holding L6, an order is refused without the principal's own authorisation."""
        g = AgentGrant(agent_id="drifted", level="L6_NORMAL_EXECUTION",
                       principal_authorised=False)
        ok, why = permitted(g, "L6_NORMAL_EXECUTION")
        assert ok is False
        assert "arming live trading is the principal's act" in why

    def test_the_principal_can_authorise(self) -> None:
        g = AgentGrant(agent_id="live", level="L6_NORMAL_EXECUTION", principal_authorised=True)
        assert permitted(g, "L6_NORMAL_EXECUTION")[0] is True


class TestEscalate:
    def test_CAPABILITY_IS_NOT_AUTHORITY(self) -> None:
        """The upgrade argument must be nameable AND still not sufficient on its own."""
        g = AgentGrant(agent_id="seat", level="L1_PRIVATE_READ")
        new, why = escalate(g, to_level="L2_RESEARCH_COMPUTE",
                            evidence=("ran 40 studies with no artifact corruption",),
                            capability_improved=True)
        assert new is not None
        assert "that was NOT the reason and must never be" in why

    def test_no_evidence_is_refused(self) -> None:
        g = AgentGrant(agent_id="seat", level="L1_PRIVATE_READ")
        new, why = escalate(g, to_level="L2_RESEARCH_COMPUTE", evidence=())
        assert new is None
        assert "a level nobody can defend later" in why

    def test_A_SKIPPED_RUNG_IS_AN_UNGOVERNED_ONE(self) -> None:
        g = AgentGrant(agent_id="seat", level="L1_PRIVATE_READ")
        new, why = escalate(g, to_level="L4_CANARY_PROPOSAL", evidence=("looks fine",))
        assert new is None
        assert "not a faster promotion, it is an ungoverned one" in why

    def test_this_function_only_promotes(self) -> None:
        g = AgentGrant(agent_id="seat", level="L3_SHADOW_ACTION")
        new, why = escalate(g, to_level="L1_PRIVATE_READ", evidence=("x",))
        assert new is None
        assert "only promotes" in why

    def test_NO_EVIDENCE_REACHES_A_CAPITAL_RUNG(self) -> None:
        """The strongest refusal in the module: this is not a technical decision."""
        g = AgentGrant(agent_id="seat", level="L4_CANARY_PROPOSAL")
        new, why = escalate(g, to_level="L5_LIMITED_EXECUTION",
                            evidence=tuple(f"proof {i}" for i in range(20)))
        assert new is None
        assert "no amount of evidence promotes a component into being able to move money" in why

    def test_a_clean_one_rung_promotion_accumulates_its_evidence(self) -> None:
        g = AgentGrant(agent_id="seat", level="L2_RESEARCH_COMPUTE", evidence=("prior",))
        new, _ = escalate(g, to_level="L3_SHADOW_ACTION", evidence=("shadowed 90 days",))
        assert new is not None
        assert new.level == "L3_SHADOW_ACTION"
        assert new.evidence == ("prior", "shadowed 90 days")


class TestLeastPrivilege:
    def test_no_excess(self) -> None:
        g = AgentGrant(agent_id="hunter", level="L0_PUBLIC_READ",
                       level_required_by_work="L0_PUBLIC_READ")
        gap, why = least_privilege_gap(g)
        assert gap == 0
        assert "no excess authority" in why

    def test_EXCESS_AUTHORITY_BUYS_NOTHING(self) -> None:
        g = AgentGrant(agent_id="hunter", level="L4_CANARY_PROPOSAL",
                       level_required_by_work="L0_PUBLIC_READ",
                       blast=BlastRadius(assessed=True, financial=0.2))
        gap, why = least_privilege_gap(g)
        assert gap == 4
        assert "the gap buys nothing" in why
        assert "SEVERE" in why

    def test_an_unmeasured_blast_radius_makes_the_gap_cost_unknown(self) -> None:
        g = AgentGrant(agent_id="x", level="L2_RESEARCH_COMPUTE",
                       level_required_by_work="L1_PRIVATE_READ")
        _, why = least_privilege_gap(g)
        assert "unknown, not small" in why


class TestSummarise:
    def test_no_declaration_is_an_unknown_state_not_a_permissive_one(self) -> None:
        r = summarise([])
        assert r["measured"] is False
        assert "not a permissive state, it is an unknown one" in str(r["headline"])

    def test_the_report_names_every_failure_class(self) -> None:
        grants = [
            AgentGrant(agent_id="gpt_hunter", level="L0_PUBLIC_READ",
                       level_required_by_work="L0_PUBLIC_READ",
                       blast=BlastRadius(assessed=True, financial=0.0001)),
            AgentGrant(agent_id="over", level="L3_SHADOW_ACTION",
                       level_required_by_work="L1_PRIVATE_READ",
                       blast=BlastRadius(assessed=True, financial=0.02)),
            AgentGrant(agent_id="drifted", level="L5_LIMITED_EXECUTION",
                       level_required_by_work="L5_LIMITED_EXECUTION",
                       blast=BlastRadius(assessed=True, financial=0.3, sandboxed=False)),
            AgentGrant(agent_id="unpriced", level="L2_RESEARCH_COMPUTE",
                       level_required_by_work="L2_RESEARCH_COMPUTE"),
        ]
        r = summarise(grants)
        assert r["measured"] is True
        assert r["over_privileged"] == ["over"]
        assert r["capital_sensitive_without_principal"] == ["drifted"]
        assert r["not_sandboxed"] == ["drifted"]
        assert r["unmeasured_blast_radius"] == ["unpriced"]
        assert "must be refused at the call site" in str(r["headline"])

    def test_an_unbounded_radius_is_listed(self) -> None:
        r = summarise([AgentGrant(agent_id="spawner", level="L2_RESEARCH_COMPUTE",
                                  level_required_by_work="L2_RESEARCH_COMPUTE",
                                  blast=BlastRadius(assessed=True, financial=0.001,
                                                    propagation=True))])
        assert r["unbounded_blast_radius"] == ["spawner"]
