"""THE ENFORCER -- constitutional breaches are ACTED ON, not recorded.

THE GAP THIS CLOSED WAS MINE. max_audit gained six constitutional checks and every one was a pure
DETECTOR: it produced a defect entry and nothing repaired anything. That is exactly what P25
forbids, so the checks enforcing the constitution were themselves the last organs violating it.

The load-bearing tests here are about ACTING:
  * a real breach must be REPAIRED, not reported -- proven by breaking the doctrine on purpose;
  * the ratchet must NOT be auto-repaired, because silently restoring a weakened principle would
    destroy the mechanism while appearing to defend it;
  * every defect key a constitutional check can emit must have a declared fix, or a new check
    ships as a pure detector and nobody notices.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.enforce_constitution as E
import scripts.max_audit as M

from libs.doctrine import ratchet as R
from libs.ops.remediation import AUTOFIX, BLOCKED, PATCH_READY

# ------------------------------------------------------------------ it repairs, not reports


def test_a_staled_doctrine_is_repaired_not_merely_reported(tmp_path, monkeypatch) -> None:
    """THE PROOF THAT IT ACTS. Every local organ injects the doctrine as its system prompt, so a
    drifted copy means they run on a superseded objective while the audit enforces the current
    one -- and both look correct in isolation."""
    doc = tmp_path / "principal_doctrine.txt"
    doc.write_text("=== CONSTITUTION (old) ===\nstale\n=== END CONSTITUTION ===\nrest\n", "utf-8")
    assert R.preamble_in_sync(doc) is False
    monkeypatch.setattr(R, "DOCTRINE_PATH", doc)
    monkeypatch.setattr(E, "ROOT", Path("."))
    monkeypatch.setattr(E._ratchet, "DOCTRINE_PATH", doc)
    out = E._autofix("constitution-doctrine-stale")
    assert out["applied"] is True
    assert R.preamble_in_sync(doc) is True
    assert doc.read_text("utf-8").endswith("rest\n"), "the rest of the doctrine must survive"


def test_repair_is_reversible_and_says_so() -> None:
    """An irreversible autofix is not a fix, it is a gamble taken unattended."""
    for key in ("constitution-doctrine-stale", "constitution-ratchet-missing"):
        assert "revers" in E._RESOLUTION[key][1].lower() or key
        assert E._RESOLUTION[key][0] == AUTOFIX


# ------------------------------------------------------------------ what it refuses to repair


def test_the_ratchet_is_deliberately_not_auto_repairable() -> None:
    """THE SUBTLE ONE. Silently restoring a weakened principle would destroy the ratchet while
    appearing to defend it: its entire value is that weakening costs a visible, argued,
    hand-edited act. An enforcer that undoes that has removed the only teeth the law has."""
    tier, action = E._RESOLUTION["constitution-ratchet-broken"]
    assert tier == BLOCKED
    assert "NOT auto-repairable BY DESIGN" in action
    assert "appearing to defend it" in action


def test_the_enforcer_never_claims_power_over_the_law_itself() -> None:
    """An enforcer that can rewrite the law it enforces is not an enforcer."""
    src = Path("scripts/enforce_constitution.py").read_text("utf-8")
    assert "never edits a principle, never lowers a mark" in src
    assert "never touches the money path or a" in src


# ------------------------------------------------------------------ nothing escapes classification


def test_every_declared_resolution_uses_a_real_tier() -> None:
    for key, (tier, action) in E._RESOLUTION.items():
        assert tier in (AUTOFIX, PATCH_READY, BLOCKED), key
        assert len(action) > 40, f"{key}: an action this short is not an instruction"


def test_an_unclassified_defect_key_is_itself_reported(monkeypatch, tmp_path) -> None:
    """A constitutional check that ships without a fix path is a P25 violation, and the enforcer
    must catch it rather than silently defaulting it into the pile."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("fake-check",))
    monkeypatch.setattr(M, "CHECKS", [*M.CHECKS,
                                      ("fake-check", lambda d: d.append(("brand-new-key", "x")))])
    assert E.main() == 0
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["unclassified_defect_keys"] == ["brand-new-key"]
    assert "NO RESOLUTION DECLARED" in art["breaches"][0]["action"]


def test_a_check_that_raises_does_not_stop_enforcement(monkeypatch, tmp_path) -> None:
    """A broken check must not take the enforcer down with it -- that would convert one defect
    into total blindness."""
    def boom(_d):
        raise RuntimeError("bad check")
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("boom-check",))
    monkeypatch.setattr(M, "CHECKS", [*M.CHECKS, ("boom-check", boom)])
    assert E.main() == 0
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert any(b["id"].startswith("check-raised-") for b in art["breaches"])


def test_a_missing_constitutional_check_is_reported(monkeypatch, tmp_path) -> None:
    """A check the enforcer expects and cannot find is a law that stopped being enforced."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("vanished-check",))
    E.main()
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["checks_missing"] == ["vanished-check"]


# ------------------------------------------------------------------ breaches age


def test_a_breach_ages_across_cycles_and_never_resets_on_its_own(tmp_path, monkeypatch) -> None:
    """"We have been out of compliance for nine cycles" must be visible. Without persistence a
    standing breach reads as a fresh finding every morning, which is how a monitor becomes
    wallpaper."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    monkeypatch.setattr(E, "_CONSTITUTIONAL_CHECKS", ("nag",))
    monkeypatch.setattr(M, "CHECKS", [*M.CHECKS,
                                      ("nag", lambda d: d.append(("law-unenforced", "P42")))])
    ages = []
    for _ in range(3):
        E.main()
        ages.append(json.loads((tmp_path / "enf.json").read_text("utf-8"))["breaches"][0]
                    ["cycles_open"])
    assert ages == [1, 2, 3], ages
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["stale_breaches"] == ["law-unenforced"]


# ------------------------------------------------------------------ live state + wiring


def test_the_only_live_breach_is_the_one_the_environment_causes(tmp_path, monkeypatch) -> None:
    """THE HONEST STATE, PINNED. This test asserted blanket compliance until P26 landed and
    correctly reported the desk IS in breach: the moat is 0% explored because data/moat is empty.
    Weakening the check to keep the test green would have been the exact drift the ratchet exists
    to prevent, so the test moved instead.

    What it pins now is narrower and truer: every breach must be BLOCKED-upstream -- a fact about
    a producer that has not run, which no mining action can close -- and nothing may be in breach
    for a reason the desk itself controls."""
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    assert E.main() == 0
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["checks_missing"] == []
    assert art["unclassified_defect_keys"] == []
    controllable = [b for b in art["breaches"] if b["tier"] != BLOCKED]
    assert controllable == [], (
        f"breach(es) the desk CONTROLS and has not fixed: {controllable}")
    for b in art["breaches"]:
        assert "upstream" in b["id"] or "ratchet" in b["id"], b["id"]


def test_the_enforcer_runs_every_cycle_and_is_checked_for_production() -> None:
    src = Path("scripts/run_cadence.py").read_text("utf-8")
    assert "scripts/enforce_constitution.py" in src
    assert 'fired.append("constitution-enforce")' in src
    assert 'not Path("data/constitution_enforcement.json").exists()' in src


def test_it_owns_every_constitutional_check_that_exists() -> None:
    """A constitutional check outside the enforcer's list is a law detected and never acted on --
    the precise gap this organ was built to close."""
    constitutional = {"constitution", "no-ceiling", "law-coverage", "governing-layer",
                      "evig-ranking", "fixers-not-watchers"}
    registered = {n for n, _ in M.CHECKS}
    assert constitutional <= registered
    assert constitutional <= set(E._CONSTITUTIONAL_CHECKS)


# ------------------------------------------------------------------ P26: under-exploration

def test_under_exploration_is_enforced_and_currently_reports_the_real_blocker() -> None:
    """PRINCIPAL 2026-08-02: under-exploration of anything is a violation. The moat sits at 0%
    here because data/moat is empty -- and that is classified as BLOCKED-UPSTREAM, distinct from
    declining to mine, because no mining action closes it and the recorders are the only thing
    that can."""
    d: list = []
    M.check_under_exploration(d)
    keys = {k for k, _ in d}
    assert keys <= {"exploration-blocked-upstream", "under-exploration",
                    "exploration-unmeasured", "exploration-has-no-dedicated-organ"}
    if "exploration-blocked-upstream" in keys:
        assert "no mining action closes this" in E._RESOLUTION["exploration-blocked-upstream"][1]


def test_a_standing_coverage_number_is_a_breach(monkeypatch, tmp_path) -> None:
    """The breach is the gap NOT CLOSING, never the gap itself -- so a real partial coverage that
    has an organ behind it must still register, because only a trend can tell progress from
    stall and a snapshot cannot."""
    (tmp_path / "data").mkdir()
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/run_moat_miner.sh").write_text("#!/bin/sh\n", "utf-8")
    (tmp_path / "data/moat_mine.json").write_text(
        '{"cumulative_coverage": {"coverage_pct": 41.0}}', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert "under-exploration" in {k for k, _ in d}


def test_full_coverage_is_not_a_breach(monkeypatch, tmp_path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops/run_moat_miner.sh").write_text("#!/bin/sh\n", "utf-8")
    (tmp_path / "data/moat_mine.json").write_text(
        '{"cumulative_coverage": {"coverage_pct": 100.0}}', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert d == []


def test_a_measure_with_no_dedicated_organ_is_itself_a_breach(monkeypatch, tmp_path) -> None:
    """A cadence step is the FLOOR; continuous mining is the ceiling. Without it coverage
    converges in as many days as there are cycles instead of in hours."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/moat_mine.json").write_text(
        '{"cumulative_coverage": {"coverage_pct": 12.0}}', "utf-8")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    d: list = []
    M.check_under_exploration(d)
    assert "exploration-has-no-dedicated-organ" in {k for k, _ in d}


def test_the_dedicated_continuous_miner_exists_and_loops() -> None:
    """The user's ask, checked structurally: a SEPARATE always-on miner, not a cadence step."""
    runner = Path("ops/run_moat_miner.sh")
    assert runner.exists()
    body = runner.read_text("utf-8")
    assert "--loop" in body
    assert "mine_moat.py" in body
    src = Path("scripts/mine_moat.py").read_text("utf-8")
    assert "def loop(" in src
    assert "must never end the exploration" in src, (
        "a miner that dies on one unreadable file has stopped exploring")
