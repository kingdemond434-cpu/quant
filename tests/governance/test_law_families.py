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
