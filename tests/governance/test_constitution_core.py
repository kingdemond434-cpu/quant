"""The immutable-core fence must FIRE. A seal that cannot detect an edit is a padlock on a hinge.

L2.8a grants the organism permission to amend its own constitution. That grant is only survivable
because five clauses are hashed and unamendable. These tests prove the hash actually discriminates:
a reflow passes, a WORD CHANGE fails, a DELETION fails, and self-resealing is not silent.
"""

from __future__ import annotations

import json

import pytest

from scripts import check_constitution_core as core


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    """A miniature constitution + its lock, so the real one is never touched by a test."""
    const = tmp_path / "CONSTITUTION.md"
    const.write_text(
        "**L1.1 THE OBJECTIVE.** Maximise expected lifetime geometric growth.\n\n"
        "**L1.2 THE HIERARCHY.** Survival first, then compounding.\n\n"
        "**L1.6 STATISTICAL VALIDATION.** Bars may rise, never fall.\n\n"
        "**L1.23 THE SURVIVAL RAILS.** Ruin probability <=2%.\n\n"
        "**L2.8a AUTONOMOUS CONSTITUTIONAL EVOLUTION.** The core is immutable.\n\n"
        "**L3.1 SOMETHING ELSE.** Not protected.\n",
        "utf-8",
    )
    lock = tmp_path / "core.lock"
    monkeypatch.setattr(core, "_CONST", const)
    monkeypatch.setattr(core, "_LOCK", lock)
    monkeypatch.setattr(core, "_ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py", "--reseal"])
    assert core.main() == 0
    return const, lock


def _verify(monkeypatch) -> int:
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py"])
    return core.main()


def test_intact_core_passes(sealed, monkeypatch):
    assert _verify(monkeypatch) == 0


def test_reflowing_a_clause_is_not_a_violation(sealed, monkeypatch):
    """Whitespace normalisation is deliberate: line-rewrapping a paragraph must not cry wolf,
    or the fence gets muted by the first cosmetic edit and then protects nothing."""
    const, _ = sealed
    const.write_text(const.read_text("utf-8").replace(
        "Maximise expected lifetime geometric growth.",
        "Maximise expected\nlifetime  geometric\n  growth."), "utf-8")
    assert _verify(monkeypatch) == 0


def test_weakening_a_rail_fails_loud(sealed, monkeypatch, capsys):
    """The exact failure L2.8a exists for: the optimiser raising a measured return by lowering
    the rail that constrains it. 2% -> 20% must not pass."""
    const, _ = sealed
    const.write_text(const.read_text("utf-8").replace("<=2%", "<=20%"), "utf-8")
    assert _verify(monkeypatch) == 1
    out = capsys.readouterr().out
    assert "CORE VIOLATION" in out and "L1.23" in out


def test_deleting_a_protected_clause_fails(sealed, monkeypatch, capsys):
    """Deletion is the cheapest attack on a hash-based seal -- no clause, no mismatch."""
    const, _ = sealed
    text = const.read_text("utf-8")
    start = text.index("**L2.8a")
    const.write_text(text[:start] + text[text.index("**L3.1"):], "utf-8")
    assert _verify(monkeypatch) == 1
    assert "DELETED" in capsys.readouterr().out


def test_drift_is_not_auto_reverted(sealed, monkeypatch):
    """A failing check must NOT silently rewrite either file. Auto-revert would let a bug erase a
    legitimate principal amendment; auto-reseal would make the fence self-defeating."""
    const, lock = sealed
    before_lock = lock.read_text("utf-8")
    const.write_text(const.read_text("utf-8").replace("<=2%", "<=20%"), "utf-8")
    assert _verify(monkeypatch) == 1
    assert lock.read_text("utf-8") == before_lock
    assert "<=20%" in const.read_text("utf-8")


def test_missing_lock_fails_and_does_not_silently_seal(sealed, monkeypatch, capsys):
    """The subtle one. Auto-sealing a missing lock reads as convenience and is a no-op fence: on a
    fresh clone or a restored box it would bless whatever constitution it found -- tampered or not
    -- and print 'intact'. A lost seal is itself the finding."""
    _, lock = sealed
    lock.unlink()
    assert _verify(monkeypatch) == 1
    assert "NO SEAL" in capsys.readouterr().out
    assert not lock.exists(), "a verify run must never create a seal"


def test_reseal_refuses_when_a_clause_is_missing(sealed, monkeypatch, capsys):
    """Sealing over a constitution that lost a protected law would bless the deletion forever."""
    const, _ = sealed
    text = const.read_text("utf-8")
    const.write_text(text[:text.index("**L1.23")] + text[text.index("**L2.8a"):], "utf-8")
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py", "--reseal"])
    assert core.main() == 2
    assert "REFUSING TO SEAL" in capsys.readouterr().out


def test_real_constitution_is_sealed_and_intact():
    """The live artifact, not a fixture: every protected clause resolves and matches its seal."""
    lock_path = core._LOCK
    assert lock_path.exists(), "data/constitution_core.lock missing -- run --reseal"
    sealed_digests = json.loads(lock_path.read_text("utf-8"))["digests"]
    now = core.current()
    assert all(v is not None for v in now.values()), f"clause not found: {now}"
    assert now == sealed_digests, "immutable constitutional core has drifted"
