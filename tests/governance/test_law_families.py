"""L1.36 -- law families enforced AS families, and the aggression family at maximum strength."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_law_families import FAMILIES, build_report
from scripts.check_timidity_language import audit_prompts, _prompt_surfaces


def test_all_six_families_fully_enforced():
    rep = build_report()
    assert rep["status"] == "OK", rep["failing"]
    assert rep["n_families"] == 6


@pytest.mark.parametrize("name", sorted(FAMILIES))
def test_family_is_complete_fenced_reaching_and_guarded(name):
    f = build_report()["families"][name]
    assert f["missing_from_constitution"] == []       # COMPLETE
    assert f["unfenced"] == []                        # ENFORCED (never prose)
    assert f["not_in_doctrine"] == []                 # REACHING every organ at spawn
    assert f["family_fence_exists"] is True           # GUARDED at family level


def test_aggression_family_holds_the_full_stack():
    members = FAMILIES["aggression"][0]
    for law in ("L1.21a", "L1.28", "L1.28a", "L1.28b", "L1.28c", "L1.25a", "L1.35"):
        assert law in members


def test_l23_reaches_the_organs_now():
    # The proving instance: fenced in the matrix, absent from doctrine, never told to an organ.
    assert "L2.3" in Path("ops/principal_doctrine.txt").read_text("utf-8")


def test_timidity_fence_sweeps_every_prompt_surface():
    surfaces = _prompt_surfaces()
    assert len(surfaces) >= 16                        # 11 miner briefs + prompts/ + organ genomes
    names = {p.name for p in surfaces}
    assert "kimi_hunter.py" in names                  # the only non-Claude hunter
    assert "deep_sweep_core.txt" in names             # the audit genome
    assert any(n.startswith("frontier_") for n in names)


def test_quota_caps_and_hedged_orders_are_caught(tmp_path, monkeypatch):
    import scripts.check_timidity_language as t
    p = tmp_path / "ops"
    p.mkdir()
    (p / "x_prompt.txt").write_text(
        "Report the top 3 findings.\nOptionally dig further if time permits.\n", "utf-8")
    monkeypatch.setattr(t, "_ROOT", tmp_path)
    monkeypatch.setattr(t, "_prompt_surfaces", lambda: [p / "x_prompt.txt"])
    kinds = {h["kind"] for h in t.audit_prompts()}
    assert kinds == {"QUOTA-CAP", "HEDGED-ORDER"}


def test_live_prompt_surfaces_are_clean():
    hits = audit_prompts()
    assert hits == [], [f"{h['file']}:{h['line']} {h['kind']}" for h in hits]


def test_breadth_per_run_stays_legal():
    # L1.35 REQUIRES runs to finish, so a per-run bound is a completion bound, not timidity.
    # Removing this exemption would make the desk's own completion contract illegal.
    src = Path("scripts/check_timidity_language.py").read_text("utf-8")
    assert "breadth-per-run" in src and "completion bound" in src


def test_fence_is_a_gate_not_a_report():
    src = Path("scripts/check_law_families.py").read_text("utf-8")
    assert 'return 2 if rep["status"] != "OK" else 0' in src
    assert "A gate, not a report" in src or "a gate, not a report" in src.lower()


# --- L1.37 continuous enforcement at every boundary --------------------------------------------

def test_law_and_state_fences_are_separated():
    from scripts.run_law_gate import _LAW_FENCES, _STATE_FENCES
    law = {f for f, _ in _LAW_FENCES}
    state = {f for f, _ in _STATE_FENCES}
    assert law and state and not (law & state)
    # law fences must be portable: they read the repo, so CI can run them meaningfully
    assert "check_constitution_core.py" in law and "check_law_families.py" in law
    # state fences measure box-only live state and must NOT gate a commit
    assert "check_exploration.py" in state and "check_conversion.py" in state


def test_laws_only_gate_passes_in_a_fresh_checkout():
    from scripts.run_law_gate import full_gate
    rep = full_gate(laws_only=True)
    assert rep["ok"] is True, rep["failures"]


def test_fast_gate_guards_core_and_doctrine():
    from scripts.run_law_gate import fast_gate
    rep = fast_gate()
    assert rep["ok"] is True, rep["failures"]


def test_unrunnable_fence_counts_as_failed_never_skipped():
    src = Path("scripts/run_law_gate.py").read_text("utf-8")
    assert "counts as FAILED, never skipped" in src
    assert "MISSING -- an absent fence is a failed fence" in src


def test_all_four_boundaries_are_wired():
    assert "run_law_gate.py --laws-only" in Path(".github/workflows/ci.yml").read_text("utf-8")
    hook = Path("deploy/git_hooks/pre-push")
    assert hook.exists() and "run_law_gate.py" in hook.read_text("utf-8")
    assert "_law_gate_fast" in Path("ops/brain_env.sh").read_text("utf-8")
    assert "run_law_gate.py" in Path("ops/crontab.manifest").read_text("utf-8")
    assert "git_hooks/pre-push" in Path("deploy/pull_deploy.sh").read_text("utf-8")


def test_spawn_gate_pages_but_does_not_block():
    # A governance fault must never silently stop the desk (L1.2).
    be = Path("ops/brain_env.sh").read_text("utf-8")
    assert "_brain_page" in be and "return 0" in be.split("_law_gate_fast()")[1][:900]


# --- L1.39 zero idle findings ------------------------------------------------------------------

def test_l39_in_conversion_family_and_mapped():
    from scripts.check_law_families import FAMILIES
    assert "L1.39" in FAMILIES["conversion"][0]
    mx = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.39"' in mx


def test_l39_draws_the_action_vs_validation_distinction():
    # The load-bearing safety line: no idle = zero ACTION latency, NOT zero validation latency.
    # Without this, "implement immediately" becomes the phantom-edge factory the desk bans.
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.39 ZERO IDLE FINDINGS" in const
    assert "never size it immediately" in const
    assert "a candidate is never an edge" in const
    doc = Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert "THE IMMEDIACY IS IN THE ROUTING, NEVER IN THE BAR" in doc
