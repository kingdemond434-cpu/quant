"""The DeepSeek local core: the five refusals that keep a second flywheel from becoming a
second desk."""
from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from libs.ops import deepseek_cycle as ds
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


# ------------------------------------------------------------------ CXCV-38 inheritance
def test_deepseek_inherits_rather_than_refounds_the_desks_registries() -> None:
    """CXCV-38: consume existing edge intake, conditional-survivor state, capability challengers
    and free-data verdicts WITHOUT creating parallel registries."""
    from libs.ops.deepseek_cycle import inheritance_check
    out = inheritance_check()
    assert out["ok"] and out["parallel_registries_found"] == []
    assert "INHERITS" in out["verdict"]


def test_a_deepseek_shadow_of_a_canonical_registry_is_a_named_defect(tmp_path: Path) -> None:
    """THE FAILURE THE MANDATE WARNS ABOUT: a second statistical universe assembled one
    well-meaning convenience at a time."""
    from libs.ops.deepseek_cycle import inheritance_check
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data/deepseek_survivors.jsonl").write_text("{}", "utf-8")
    out = inheritance_check(tmp_path)
    assert not out["ok"]
    assert "PARALLEL REGISTRY DEFECT" in out["verdict"]
    assert "data/deepseek_survivors.jsonl" in out["parallel_registries_found"]


def test_an_absent_canonical_registry_is_not_an_inheritance_failure(tmp_path: Path) -> None:
    """Asymmetric on purpose: absence of a canonical file is a fact about the desk's history;
    presence of a parallel one is a fact about this agent's behaviour."""
    from libs.ops.deepseek_cycle import inheritance_check
    out = inheritance_check(tmp_path)
    assert out["ok"] and out["inherited_absent"]


def test_the_inherited_list_names_what_each_registry_carries() -> None:
    from libs.ops.deepseek_cycle import INHERITED_REGISTRIES
    assert len(INHERITED_REGISTRIES) >= 6
    assert all(path.strip() and what.strip() for path, what in INHERITED_REGISTRIES)


# ------------------------------------------------------------------ run_role: the missing step 4/5
class TestRunRole:
    """2026-08-20: main() previously stopped at 'READY' -- 'cold phase and routing run here' was
    a comment. run_role() is what it should have called. Every gate composed here was already
    tested above in isolation; these tests exercise the composition and the one genuinely new
    piece (the actual call + routing), never a live network call."""

    _LIT_ENV: ClassVar[dict[str, str]] = {
        "OPENROUTER_API_KEY": "sk-test", "DEEPSEEK_BULK_MODEL": "deepseek/bulk-x",
        "DEEPSEEK_DEEP_MODEL": "deepseek/deep-x",
    }

    def test_dark_seat_short_circuits_before_any_call(self) -> None:
        from libs.ops.deepseek_cycle import run_role
        out = run_role("cold_alpha_inventor", "brief", deep=False, env={})
        assert out["status"] == "DARK"

    def test_lit_seat_missing_the_drawn_models_env_var_is_model_unavailable(self) -> None:
        from libs.ops.deepseek_cycle import run_role
        out = run_role("cold_alpha_inventor", "brief", deep=True,
                       env={"OPENROUTER_API_KEY": "sk-test", "DEEPSEEK_BULK_MODEL": "b"})
        assert out["status"] == "MODEL_UNAVAILABLE"
        assert "DEEPSEEK_DEEP_MODEL" in out["why"]

    def test_a_failed_policy_gate_blocks_before_any_call(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        import libs.ops.deepseek_cycle as ds_mod
        monkeypatch.setattr(ds_mod, "policy_gate",
                            lambda root=None: {"ok": False, "why": "MISSING_POLICY (test)"})
        out = ds_mod.run_role("cold_alpha_inventor", "brief", deep=False,
                              env=self._LIT_ENV, root=tmp_path)
        assert out["status"] == "BLOCKED_POLICY"

    def test_an_exhausted_budget_blocks_before_any_call(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        import libs.ops.deepseek_cycle as ds_mod
        monkeypatch.setattr(ds_mod, "policy_gate",
                            lambda root=None: {"ok": True, "policy_hash": "h"})
        monkeypatch.setattr(ds_mod, "budget_gate",
                            lambda: {"ok": False, "why": "BUDGET_EXHAUSTED (test)"})
        out = ds_mod.run_role("cold_alpha_inventor", "brief", deep=False,
                              env=self._LIT_ENV, root=tmp_path)
        assert out["status"] == "BUDGET_EXHAUSTED"

    def _pass_gates(self, monkeypatch: pytest.MonkeyPatch, ds_mod) -> None:
        monkeypatch.setattr(ds_mod, "policy_gate",
                            lambda root=None: {"ok": True, "policy_hash": "test-hash"})
        monkeypatch.setattr(ds_mod, "budget_gate",
                            lambda: {"ok": True, "why": "$0.00 of $20.00 spent this month"})

    def test_a_call_failure_is_reported_never_raised(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        import libs.ops.deepseek_cycle as ds_mod
        import libs.ops.llm_seat as llm_seat_mod
        self._pass_gates(monkeypatch, ds_mod)
        monkeypatch.setattr(llm_seat_mod, "chat", lambda *a, **kw: ("", "monthly cap reached"))
        out = ds_mod.run_role("cold_alpha_inventor", "brief", deep=False,
                              env=self._LIT_ENV, root=tmp_path)
        assert out["status"] == "CALL_FAILED" and "monthly cap" in out["why"]

    def test_a_malformed_response_yields_zero_findings_not_a_crash(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        import libs.ops.deepseek_cycle as ds_mod
        import libs.ops.llm_seat as llm_seat_mod
        self._pass_gates(monkeypatch, ds_mod)
        monkeypatch.setattr(llm_seat_mod, "chat", lambda *a, **kw: ("not json at all", None))
        out = ds_mod.run_role("cold_alpha_inventor", "brief", deep=False,
                              env=self._LIT_ENV, root=tmp_path)
        assert out["status"] == "OK" and out["n_findings"] == 0

    def test_a_genuine_finding_is_written_to_deepseeks_own_evidence_store(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """The evidence store is sanctioned (EVIDENCE, distinct from every _FORBIDDEN_PARALLELS
        path) -- this is the one new artifact this build introduces, and it must actually land."""
        import json as _json

        import libs.ops.deepseek_cycle as ds_mod
        import libs.ops.llm_seat as llm_seat_mod
        self._pass_gates(monkeypatch, ds_mod)
        payload = _json.dumps({"findings": [
            {"title": "weekend gap fade on XAUUSD", "mechanism": "forced deleveraging into the "
             "Friday close reopens with a measurable mean-reverting gap",
             "testable_claim": "gap direction predicts the first 2h return, |t|>2",
             "capability_source": None, "evidence_grade": None}]})
        monkeypatch.setattr(llm_seat_mod, "chat", lambda *a, **kw: (payload, None))
        out = ds_mod.run_role("cold_alpha_inventor", "brief", deep=False,
                              env=self._LIT_ENV, root=tmp_path)
        assert out["status"] == "OK"
        assert out["n_findings"] == 1
        assert out["routed_titles"] == ["weekend gap fade on XAUUSD"]
        assert out["capability_walks_proposed"] == 0
        rows = (tmp_path / ds_mod.EVIDENCE).read_text("utf-8").splitlines()
        assert len(rows) == 1
        row = _json.loads(rows[0])
        assert row["role"] == "cold_alpha_inventor" and row["deep"] is False
        assert row["authority"] == "ALLOWED_RESEARCH_ONLY"

    def test_a_finding_naming_a_capability_source_also_proposes_a_challenger_walk(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """The reverse-engineering path (principal 2026-08-20): a finding that names a real
        capability source is a High-Flyer-class walk candidate, routed into
        capability_challenger's own register() -- validated, never auto-adopted."""
        import json as _json

        import libs.ops.deepseek_cycle as ds_mod
        import libs.ops.llm_seat as llm_seat_mod
        self._pass_gates(monkeypatch, ds_mod)
        payload = _json.dumps({"findings": [
            {"title": "systematic factor-mining at industrial scale", "mechanism": "compute "
             "advantage lets many more hypotheses clear the same statistical bar per unit time",
             "testable_claim": "marginal E[log W] per research-hour rises with parallel test "
             "throughput, holding the multiplicity correction fixed",
             "capability_source": "High-Flyer", "evidence_grade": "CREDIBLE_PRESS_REPORT"}]})
        monkeypatch.setattr(llm_seat_mod, "chat", lambda *a, **kw: (payload, None))
        out = ds_mod.run_role("research_technology_hunter", "brief", deep=True,
                              env=self._LIT_ENV, root=tmp_path)
        assert out["status"] == "OK" and out["capability_walks_proposed"] == 1
        rows = (tmp_path / ds_mod.CAPABILITY_LEDGER).read_text("utf-8").splitlines()
        assert len(rows) == 1
        row = _json.loads(rows[0])
        assert row["status"] == "PROPOSED_UNBENCHMARKED"
        assert row["capability"]["source"] == "High-Flyer"
        assert row["capability"]["evidence_grade"] == "CREDIBLE_PRESS_REPORT"
        assert row["registration"]["status"] == "REGISTERED"

    def test_an_invalid_evidence_grade_is_never_invented_as_something_stronger(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        import json as _json

        import libs.ops.deepseek_cycle as ds_mod
        import libs.ops.llm_seat as llm_seat_mod
        self._pass_gates(monkeypatch, ds_mod)
        payload = _json.dumps({"findings": [
            {"title": "x", "mechanism": "y", "testable_claim": "z",
             "capability_source": "Some Fund", "evidence_grade": "TOTALLY_CONFIRMED"}]})
        monkeypatch.setattr(llm_seat_mod, "chat", lambda *a, **kw: (payload, None))
        ds_mod.run_role("cold_alpha_inventor", "brief", deep=False,
                        env=self._LIT_ENV, root=tmp_path)
        row = _json.loads((tmp_path / ds_mod.CAPABILITY_LEDGER).read_text("utf-8").splitlines()[0])
        assert row["capability"]["evidence_grade"] == "ANONYMOUS_RUMOR"

    def test_the_cold_context_actually_reaches_the_prompt_with_contamination_stripped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        import json as _json

        import libs.ops.deepseek_cycle as ds_mod
        import libs.ops.llm_seat as llm_seat_mod
        self._pass_gates(monkeypatch, ds_mod)
        captured: dict = {}

        def fake_chat(prompt, *, system="", **kw):
            captured["prompt"] = prompt
            captured["system"] = system
            return (_json.dumps({"findings": []}), None)

        monkeypatch.setattr(llm_seat_mod, "chat", fake_chat)
        state = {"measured_sharpe": 1.2, "claude_opinion": "this looks promising"}
        ds_mod.run_role("cold_alpha_inventor", "brief", deep=False,
                        env=self._LIT_ENV, root=tmp_path, state=state)
        assert "measured_sharpe" in captured["prompt"]
        assert "claude_opinion" not in captured["prompt"]
        assert "this looks promising" not in captured["prompt"]

    def test_a_resealed_run_id_with_different_content_is_a_conflict_not_a_silent_overwrite(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        import json as _json

        import libs.ops.deepseek_cycle as ds_mod
        import libs.ops.llm_seat as llm_seat_mod
        self._pass_gates(monkeypatch, ds_mod)
        calls = iter([_json.dumps({"findings": []}), _json.dumps({"findings": [
            {"title": "different", "mechanism": "m", "testable_claim": "t"}]})])
        monkeypatch.setattr(llm_seat_mod, "chat", lambda *a, **kw: (next(calls), None))
        first = ds_mod.run_role("cold_alpha_inventor", "brief", deep=False, env=self._LIT_ENV,
                                root=tmp_path, run_id="fixed-id")
        assert first["status"] == "OK"
        second = ds_mod.run_role("cold_alpha_inventor", "brief", deep=False, env=self._LIT_ENV,
                                 root=tmp_path, run_id="fixed-id")
        assert second["status"] == "SEAL_CONFLICT"


class TestDonation:
    """The flywheel published nothing for the life of it, and reported success.

    Its donate step is `git add -- data/ docs/research/`, and every DeepSeek output store was
    matched by `.gitignore:11 data/*`. `git add` on an ignored path is a SILENT NO-OP, so the
    cycle ran daily, committed, pushed, and shipped none of its own findings -- while the commits
    it made carried other organs' files swept up by the same blanket add. Findings now go to
    `data/intelligence/deepseek/`, which is allowlisted AND is the tree
    `miner_candidate_compiler` globs, so one write fixes visibility and conversion together.
    """

    _LIT: ClassVar[dict[str, str]] = dict(TestRunRole._LIT_ENV)

    def _run(self, tmp_path, monkeypatch, reply: str):
        monkeypatch.setattr(ds, "policy_gate", lambda root=None: {"ok": True, "policy_hash": "h"})
        monkeypatch.setattr(ds, "budget_gate", lambda: {"ok": True, "why": ""})
        from libs.ops import llm_seat
        monkeypatch.setattr(llm_seat, "chat", lambda *a, **k: (reply, ""))
        return ds.run_role("cold_alpha_inventor", "invent", deep=False, state={},
                           root=tmp_path, env=dict(self._LIT))

    def test_a_finding_is_published_where_every_brain_can_read_it(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch, json.dumps({"findings": [
            {"title": "JPY month-end fixing drift", "mechanism": "forced rebalancing",
             "testable_claim": "drift is positive", "symbols": ["USDJPY"],
             "family": "session_range_breakout"}]}))
        assert out["status"] == "OK"
        assert out["donated_to"], "a finding that is not donated is a finding nobody receives"
        donated = sorted((tmp_path / ds.DONATE_DIR).glob("discoveries_*.json"))
        assert donated, "nothing written to the donation directory"
        doc = json.loads(donated[0].read_text(encoding="utf-8"))
        assert doc["source"] == "deepseek"
        row = doc["discoveries"][0]
        assert row["symbols"] == ["USDJPY"], "symbols must survive to the compiler"
        assert row["family"] == "session_range_breakout"

    def test_the_donation_lands_in_the_tree_the_compiler_globs(self, tmp_path, monkeypatch):
        """Not a new pipeline -- the existing one. The compiler walks data/intelligence/*/."""
        self._run(tmp_path, monkeypatch, json.dumps({"findings": [
            {"title": "t", "mechanism": "m", "testable_claim": "c", "symbols": ["EURUSD"]}]}))
        written = sorted(
            (tmp_path / "data" / "intelligence" / "deepseek").glob("discoveries_*.json"))
        assert written, "must be under data/intelligence/<source>/discoveries_*.json"

    def test_a_general_finding_still_publishes_and_becomes_a_deepening_task(self, tmp_path,
                                                                           monkeypatch):
        """No symbols is honest, not a reason to drop it -- the reader works it later."""
        out = self._run(tmp_path, monkeypatch, json.dumps({"findings": [
            {"title": "carry crowding", "mechanism": "m", "testable_claim": "c", "symbols": []}]}))
        assert out["donated_to"]
        doc = json.loads(sorted((tmp_path / ds.DONATE_DIR).glob("*.json"))[0].read_text("utf-8"))
        assert doc["discoveries"][0]["symbols"] == []

    def test_no_findings_writes_no_file(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch, json.dumps({"findings": []}))
        assert out["donated_to"] is None
        assert not list((tmp_path / ds.DONATE_DIR).glob("*.json"))

    def test_a_missing_challenger_module_costs_the_walk_not_the_cycle(self, tmp_path, monkeypatch):
        """The absent module raised for EVERY finding naming a source -- which the prompt asks
        for."""
        import builtins
        real = builtins.__import__

        def no_challenger(name, *a, **k):
            if "capability_challenger" in name:
                raise ImportError("No module named 'libs.research.capability_challenger'")
            return real(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", no_challenger)
        out = self._run(tmp_path, monkeypatch, json.dumps({"findings": [
            {"title": "t", "mechanism": "m", "testable_claim": "c", "symbols": ["EURUSD"],
             "capability_source": "Renaissance", "evidence_grade": "PEER_REPORTED"}]}))
        assert out["status"] == "OK", "a missing enrichment must not crash the cycle"
        assert out["donated_to"], "the finding must still be donated"
