"""THE DESK HASH-LOCKED ITS LAWS AND LEFT THE KILL SWITCH ON AN HONOUR SYSTEM.

Audited 2026-08-08. `check_constitution_core.py` verifies five constitutional clauses by SHA-256
and fails the build if a word moves. The code that enforces SURVIVAL was protected by prose:

    ops/run_recommendation_worker.sh:99   "is Tier-3 -- do NOT edit it"
    scripts/watchdog.py:258               "TIER-3 never-touch"

Every one of those is an instruction to a reader; none is a mechanism. Locking the laws and not
the kill switch is the wrong way round -- prose can be re-argued, and a flattened book cannot.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import scripts.check_risk_kernel as RK


def test_THE_TIER3_RUIN_RAIL_IS_IN_THE_KERNEL() -> None:
    """The one control that ENDS a losing session rather than reducing it."""
    assert "scripts/run_deadman_switch.py" in RK.KERNEL
    assert "TIER-3" in RK.KERNEL["scripts/run_deadman_switch.py"]


def test_EVERY_KERNEL_FILE_STATES_WHY_IT_IS_ONE() -> None:
    """A list of paths with no reasons is a list somebody prunes to make a refactor pass."""
    for rel, why in RK.KERNEL.items():
        assert len(why) > 40, f"{rel} has no substantive reason"


def test_EVERY_KERNEL_FILE_ACTUALLY_EXISTS() -> None:
    """A named-but-absent rail would silently drop out of protection."""
    for rel in RK.KERNEL:
        assert (Path(rel)).exists(), f"{rel} is named as a kernel file and is not on disk"


def test_THE_REPO_IS_CURRENTLY_LOCKED_AND_INTACT() -> None:
    drifted, missing, unlocked = RK.verify()
    assert missing == [], f"a survival rail is ABSENT: {missing}"
    assert unlocked == [], f"kernel files carry no protection: {unlocked}"
    assert drifted == [], f"the survival path changed without being re-locked: {drifted}"


def test_AN_ABSENT_FILE_HASHES_TO_NONE_NOT_A_SENTINEL(tmp_path) -> None:
    """A missing survival file must never compare equal to anything: deleted, edited and fine are
    three different states and must look different."""
    assert RK.digest(tmp_path / "nope.py") is None


def test_LINE_ENDING_CHECKOUT_CONVERSION_IS_NOT_FALSE_TAMPERING(tmp_path) -> None:
    rail = tmp_path / "rail.py"
    rail.write_bytes(b"first\nsecond\n")
    canonical = RK.digest(rail)
    rail.write_bytes(b"first\r\nsecond\r\n")
    assert RK.digest(rail) == canonical


def test_A_MODIFIED_RAIL_IS_DETECTED(tmp_path, monkeypatch) -> None:
    """The property the whole check exists for."""
    f = tmp_path / "rail.py"
    f.write_text("original", "utf-8")
    manifest = tmp_path / "lock.json"
    monkeypatch.setattr(RK, "ROOT", tmp_path)
    monkeypatch.setattr(RK, "MANIFEST", manifest)
    monkeypatch.setattr(RK, "KERNEL", {"rail.py": "a test rail with a stated reason for existing"})
    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", "baseline"])
    assert RK.main() == 0
    assert RK.verify() == ([], [], [])
    f.write_text("modified by an organ that never read the comment", "utf-8")
    drifted, _missing, _unlocked = RK.verify()
    assert drifted == ["rail.py"]


def test_A_DELETED_RAIL_IS_THE_MOST_SERIOUS_FINDING(tmp_path, monkeypatch, capsys) -> None:
    f = tmp_path / "rail.py"
    f.write_text("x", "utf-8")
    monkeypatch.setattr(RK, "ROOT", tmp_path)
    monkeypatch.setattr(RK, "MANIFEST", tmp_path / "lock.json")
    monkeypatch.setattr(RK, "KERNEL", {"rail.py": "a test rail with a stated reason for existing"})
    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", "baseline"])
    RK.main()
    f.unlink()
    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py"])
    assert RK.main() == 1
    out = capsys.readouterr().out
    assert "MISSING" in out and "is not on disk" in out


def test_RE_LOCKING_REQUIRES_A_REASON(tmp_path, monkeypatch, capsys) -> None:
    """A rail re-locked with no recorded reason is a change nobody can audit later -- which is the
    state this check exists to end."""
    monkeypatch.setattr(RK, "MANIFEST", tmp_path / "lock.json")
    monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", "  "])
    assert RK.main() == 2
    assert "REFUSED" in capsys.readouterr().out


def test_THE_LOCK_KEEPS_A_HISTORY(tmp_path, monkeypatch) -> None:
    """Every re-lock is an amendment and the record of amendments is the audit trail."""
    f = tmp_path / "rail.py"
    f.write_text("x", "utf-8")
    manifest = tmp_path / "lock.json"
    monkeypatch.setattr(RK, "ROOT", tmp_path)
    monkeypatch.setattr(RK, "MANIFEST", manifest)
    monkeypatch.setattr(RK, "KERNEL", {"rail.py": "a test rail with a stated reason for existing"})
    for reason in ("first", "second"):
        monkeypatch.setattr(sys, "argv", ["check_risk_kernel.py", "--update", "--reason", reason])
        RK.main()
    hist = json.loads(manifest.read_text())["history"]
    assert [h["reason"] for h in hist] == ["first", "second"]


def test_IT_IS_HONEST_ABOUT_BEING_TAMPER_EVIDENT_NOT_TAMPER_PROOF() -> None:
    """True tamper-proofing is a privilege boundary -- separate credentials, a service the research
    account cannot redeploy. Claiming more than the mechanism delivers would be worse than the gap.
    """
    src = Path("scripts/check_risk_kernel.py").read_text("utf-8")
    assert "TAMPER-EVIDENT, not tamper-PROOF" in src
    assert "privilege boundary" in src
