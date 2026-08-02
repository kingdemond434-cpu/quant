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


def test_the_desk_is_currently_constitutionally_compliant(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(E, "OUT", tmp_path / "enf.json")
    monkeypatch.setattr(E, "BREACHES", tmp_path / "br.json")
    assert E.main() == 0
    art = json.loads((tmp_path / "enf.json").read_text("utf-8"))
    assert art["compliant"], art["breaches"]
    assert art["checks_missing"] == []


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
