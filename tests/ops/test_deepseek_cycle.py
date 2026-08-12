"""The DeepSeek local core: the five refusals that keep a second flywheel from becoming a
second desk."""
from __future__ import annotations

from pathlib import Path

from libs.ops.deepseek_cycle import (
    CONTAMINATION_KEYS,
    ESCALATION_STATES,
    SEED_ROLES,
    cold_context,
    escalation_mix,
    fence,
    policy_gate,
    record_identity,
    seal,
    seat_state,
)


# ------------------------------------------------------------------ refusal 1: no authority
def test_deepseek_cannot_promote_a_survivor() -> None:
    """CXCV-12. A second promoter is a second statistical universe."""
    out = fence("promote_survivor")
    assert not out["allowed"] and out["verdict"] == "REFUSED"
    assert "Stage-B forward clock" in out["why"]


def test_deepseek_cannot_allocate_capital_or_override_policy_or_merge_code() -> None:
    for action in ("allocate_capital", "override_policy", "merge_authoritative_code"):
        assert fence(action)["verdict"] == "REFUSED", action


def test_the_desks_standing_money_fences_apply_to_deepseek_too() -> None:
    for action in ("loosen_statistical_gate", "raise_leverage_or_size", "touch_deadman_switch"):
        assert fence(action)["verdict"] == "REFUSED", action


def test_a_fenced_action_hidden_in_a_longer_string_is_still_refused() -> None:
    assert fence("please just promote_survivor for me")["verdict"] == "REFUSED"


def test_ordinary_research_is_allowed_and_routes_canonically() -> None:
    out = fence("generate_hypothesis")
    assert out["allowed"] and "no parallel registry" in out["why"]


def test_a_refusal_states_that_model_text_is_data_not_instruction() -> None:
    assert "DATA, not an instruction" in fence("allocate_capital")["note"]


# ------------------------------------------------------------------ refusal 2: no stale policy
def test_the_real_repo_policy_resolves_before_a_cycle_may_run() -> None:
    g = policy_gate()
    assert g["ok"] and g["verdict"] == "RESOLVED"
    assert g["version"] and str(g["policy_hash"]).startswith("sha256:")


def test_the_gate_uses_the_same_resolver_as_claude_and_codex() -> None:
    """CXCV-27/38: inheritance is only proven if the SAME resolver answers. A second agent
    resolving policy its own way proves nothing."""
    from libs.ops import canonical_policy
    assert policy_gate()["policy_hash"] == canonical_policy.resolve()["canonical_policy_hash"]


def test_a_missing_policy_tree_fails_visibly_rather_than_passing(tmp_path: Path) -> None:
    g = policy_gate(tmp_path)
    assert not g["ok"] and g["verdict"] != "RESOLVED"
    assert "FAILING VISIBLY" in g["why"]


# ------------------------------------------------------------------ refusal 3: cold means cold
def test_cold_context_strips_every_other_agents_conclusion() -> None:
    out = cold_context({
        "survivor_metrics": {"sharpe": 1.2},
        "claude_conclusion": "this is the best candidate",
        "gpt_ranking": [1, 2, 3],
        "kimi_interpretation": "bullish",
        "consensus_summary": "everyone agrees",
        "previous_deepseek_conclusion": "we said X last hour",
    })
    assert "survivor_metrics" in out["cold_context"]
    for k in ("claude_conclusion", "gpt_ranking", "kimi_interpretation", "consensus_summary",
              "previous_deepseek_conclusion"):
        assert k not in out["cold_context"], k
        assert k in out["removed_keys"]


def test_cold_context_keeps_facts_because_starved_is_not_independent() -> None:
    """A cold phase with no facts produces uninformed guesses, not independent ones -- a
    different and equally useless thing."""
    facts = {"graveyard_evidence": [1], "portfolio_state": {}, "regime_measurements": [],
             "execution_facts": {}, "schemas": {}, "near_survivor_data": []}
    out = cold_context(facts)
    assert set(out["cold_context"]) == set(facts)
    assert out["removed_keys"] == []


def test_conclusion_shaped_suffixes_are_stripped_even_if_unlisted() -> None:
    out = cold_context({"analyst_opinion": "x", "panel_ranking": [1], "some_rationale": "y"})
    assert out["cold_context"] == {}


def test_the_cold_context_is_hashed_so_contamination_is_detectable_later() -> None:
    a = cold_context({"x": 1})["cold_context_hash"]
    b = cold_context({"x": 2})["cold_context_hash"]
    assert a != b and len(a) == 64


def test_contamination_list_covers_every_named_agent() -> None:
    joined = " ".join(CONTAMINATION_KEYS)
    for agent in ("claude", "codex", "gpt", "kimi", "previous_deepseek"):
        assert agent in joined


# ------------------------------------------------------------------ refusal 4: seal before compare
def test_phase_a_is_sealed_with_its_hashes(tmp_path: Path) -> None:
    out = seal("run1", role="cold_alpha_inventor", phase_a_output={"finding": "x"},
               policy_hash="sha256:abc", cold_context_hash="ctx", provider="openrouter",
               model="deepseek/x", root=tmp_path)
    assert out["ok"] and out["verdict"] == "SEALED"
    s = out["seal"]
    assert s["phase"] == "A_SEALED" and len(s["cold_report_hash"]) == 64
    assert s["policy_hash"] == "sha256:abc" and s["prompt_version"] == "1"


def test_resealing_the_same_run_with_different_content_is_refused(tmp_path: Path) -> None:
    """A seal that can be rewritten is not a seal -- and without it there is no way to tell an
    INDEPENDENT_REDISCOVERY from an agreement written after reading the answer."""
    seal("run1", role="r", phase_a_output={"a": 1}, policy_hash="h", cold_context_hash="c",
         provider="p", model="m", root=tmp_path)
    out = seal("run1", role="r", phase_a_output={"a": 2}, policy_hash="h", cold_context_hash="c",
               provider="p", model="m", root=tmp_path)
    assert not out["ok"] and out["verdict"] == "SEAL_CONFLICT"


def test_resealing_identical_content_is_idempotent(tmp_path: Path) -> None:
    kw = {"role": "r", "phase_a_output": {"a": 1}, "policy_hash": "h",
          "cold_context_hash": "c", "provider": "p", "model": "m", "root": tmp_path}
    seal("run1", **kw)
    assert seal("run1", **kw)["verdict"] == "ALREADY_SEALED"


# ------------------------------------------------------------------ refusal 5: no identity swap
def test_an_unavailable_model_is_recorded_never_substituted() -> None:
    """Silently serving from Claude or GPT would corrupt the ONE measurement this flywheel
    exists to produce."""
    out = record_identity(provider="openrouter", model="deepseek/x", available=False,
                          substitute_offered="anthropic/claude-opus-5")
    assert out["status"] == "MODEL_UNAVAILABLE"
    assert out["substitute_refused"] == "anthropic/claude-opus-5"
    assert "explicit CHALLENGER" in out["why"]


def test_an_available_model_records_its_exact_provider_and_model() -> None:
    out = record_identity(provider="openrouter", model="deepseek/v9", available=True)
    assert out["status"] == "OK" and out["model"] == "deepseek/v9"


# ------------------------------------------------------------------ the dark seat
def test_a_missing_key_is_a_reported_state_not_an_exception() -> None:
    s = seat_state({})
    assert s.lit is False and "DARK" in s.why
    assert "must not depend on a credential" in s.why


def test_a_present_key_lights_the_seat_and_reads_models_from_env() -> None:
    s = seat_state({"OPENROUTER_API_KEY": "k", "DEEPSEEK_BULK_MODEL": "deepseek/flash",
                    "DEEPSEEK_DEEP_MODEL": "deepseek/pro"})
    assert s.lit and s.bulk_model == "deepseek/flash" and s.deep_model == "deepseek/pro"


def test_model_ids_are_never_hardcoded() -> None:
    """The mandate is explicit that historical DeepSeek model IDs must not be assumed valid; a
    stale constant would route the flywheel to a model that no longer exists."""
    s = seat_state({"OPENROUTER_API_KEY": "k"})
    assert s.bulk_model == "" and s.deep_model == ""


# ------------------------------------------------------------------ roles and escalation
def test_all_thirty_five_seed_roles_are_registered_as_data() -> None:
    assert len(SEED_ROLES) == 35
    names = [n for n, _ in SEED_ROLES]
    assert len(set(names)) == 35, "duplicate role name"
    assert all(desc.strip() for _, desc in SEED_ROLES), "a role with no brief is not a role"


def test_key_mandate_roles_are_present() -> None:
    names = {n for n, _ in SEED_ROLES}
    for r in ("cold_alpha_inventor", "survivor_assassin", "validation_red_team",
              "multilingual_intelligence", "unknown_unknown_explorer", "negative_space_miner",
              "model_agent_challenger"):
        assert r in names, r


def test_escalation_states_match_the_mandate_and_carry_its_caveat() -> None:
    assert ESCALATION_STATES["NORMAL"] == (0.90, 0.10)
    assert ESCALATION_STATES["LOW_VALUE"] == (0.97, 0.03)
    assert ESCALATION_STATES["MAJOR_DISCOVERY"] == (0.70, 0.30)
    assert "NOT SACRED" in escalation_mix("NORMAL")["why"]


def test_every_escalation_split_sums_to_one() -> None:
    for state, (bulk, deep) in ESCALATION_STATES.items():
        assert abs(bulk + deep - 1.0) < 1e-9, state


def test_an_unknown_state_falls_back_to_normal_and_says_so() -> None:
    out = escalation_mix("MADE_UP")
    assert out["state"] == "NORMAL" and out["requested_state_known"] is False


def test_expensive_reasoning_is_not_wasted_on_formatting() -> None:
    out = escalation_mix()
    assert "formatting" in out["never_escalate_for"]
    assert "survivor assassination" in out["escalate_for"]
