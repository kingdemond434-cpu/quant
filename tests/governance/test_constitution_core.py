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
    master = tmp_path / core._MASTER_REL
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text(
        "SINGLE AUTHORITATIVE TOP-LEVEL OPERATING CONSTITUTION\n"
        "24 HOURS PER DAY.\nCONSTITUTION FREEZE DEFAULT\nFREEZE PROSE.\n"
        + "\n".join(f"# {i}. SECTION" for i in range(218)),
        "utf-8",
    )
    _write_doctrine(tmp_path)
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py", "--reseal"])
    assert core.main() == 0
    return const, lock


def _write_doctrine(root, *, body: list[str] | None = None) -> None:
    """The doctrine as it really is: a large file with the immutable block somewhere inside it.

    The surrounding prose matters to the fixture. The seal covers the DELIMITED BLOCK only, so a
    fixture that was nothing but the block could not catch a seal accidentally widened to the whole
    file -- which would be red on the first duty appended and then switched off (L1.43).
    """
    lines = body or [f"  RULE {i}: a load-bearing sentence of the core." for i in range(27)]
    path = root / core._DOCTRINE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "PRINCIPAL DOCTRINE -- preamble that legitimately changes every week.\n"
        f"{core._DOCTRINE_OPEN}, governs every answer you give) ===\n"
        + "\n".join(lines) + "\n"
        + f"{core._DOCTRINE_CLOSE}\n"
        "MINING DUTY -- more prose appended by a later cycle.\n",
        "utf-8",
    )


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


def test_authoritative_master_is_complete_and_principal_sealed():
    """The 24/7 top-level authority must be complete, present and part of the immutable seal."""
    master, errors = core.master_current()
    assert errors == []
    assert master is not None and master["sections"] == 218
    lock = json.loads(core._LOCK.read_text("utf-8"))
    assert lock.get("master") == master


def test_master_word_change_fails_the_same_entry_gate(sealed, monkeypatch, capsys):
    """A controller cannot silently replace the master while leaving the compact L1 core intact."""
    root = core._ROOT
    (root / "AGENTS.md").write_text("read master", "utf-8")
    master = root / core._MASTER_REL
    phrases = (
        "SINGLE AUTHORITATIVE TOP-LEVEL OPERATING CONSTITUTION\n"
        "24 HOURS PER DAY.\nCONSTITUTION FREEZE DEFAULT\nFREEZE PROSE.\n"
    )
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text(phrases + "\n".join(f"# {i}. SECTION" for i in range(218)), "utf-8")
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py", "--reseal"])
    assert core.main() == 0
    master.write_text(master.read_text("utf-8").replace("24 HOURS", "23 HOURS"), "utf-8")
    assert _verify(monkeypatch) == 1
    assert "MASTER VIOLATION" in capsys.readouterr().out


def test_master_seal_is_stable_across_lf_and_crlf(sealed, monkeypatch):
    """Git newline conversion cannot manufacture a breach on a different controller host."""
    root = core._ROOT
    master = root / core._MASTER_REL
    text = master.read_text("utf-8")
    before, errors = core.master_current()
    assert errors == []
    master.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    after, errors = core.master_current()
    assert errors == [] and after == before
    assert _verify(monkeypatch) == 0


def test_missing_master_always_fails_even_without_agents_file(sealed, monkeypatch, capsys):
    """Authority cannot disappear by deleting both the master and its read-first pointer."""
    root = core._ROOT
    (root / core._MASTER_REL).unlink()
    agents = root / "AGENTS.md"
    if agents.exists():
        agents.unlink()
    assert _verify(monkeypatch) == 1
    assert "MASTER VIOLATION" in capsys.readouterr().out


def test_truncated_master_fails(sealed, monkeypatch, capsys):
    """A partial restore cannot pass merely because the title and load-bearing phrases survived."""
    master = core._ROOT / core._MASTER_REL
    lines = master.read_text("utf-8").splitlines()
    master.write_text("\n".join(lines[:120]) + "\n", "utf-8")
    assert _verify(monkeypatch) == 1
    assert "section sequence" in capsys.readouterr().out


def test_master_without_seal_fails(sealed, monkeypatch, capsys):
    """A present authority is not trusted unless the committed principal seal names it."""
    _, lock = sealed
    payload = json.loads(lock.read_text("utf-8"))
    payload.pop("master")
    lock.write_text(json.dumps(payload), "utf-8")
    assert _verify(monkeypatch) == 1
    assert "no principal seal" in capsys.readouterr().out


# --- R0392: the doctrine's own immutable block, the copy that is INJECTED into every organ -------


def test_editing_the_injected_core_fails_loud(sealed, monkeypatch, capsys):
    """The defect R0392 exists for: an agent silently rewriting text that calls itself immutable.

    This is the one that decides whether the seal is worth anything. The doctrine block is what
    `brain_env.sh` appends to every seat's system prompt, so a word changed here changes what the
    whole desk believes -- while `docs/CONSTITUTION.md` and the master both stay bit-identical and
    the fence, before this, printed "core intact".
    """
    body = [f"  RULE {i}: a load-bearing sentence of the core." for i in range(27)]
    body[3] = "  RULE 3: the rails MAY be loosened when the evidence is encouraging."
    _write_doctrine(core._ROOT, body=body)
    assert _verify(monkeypatch) == 1
    out = capsys.readouterr().out
    assert "DOCTRINE VIOLATION" in out and "either direction" in out


def test_reflowing_the_injected_core_is_not_a_violation(sealed, monkeypatch):
    """Same whitespace tolerance the clauses get -- a fence that cries wolf on a re-wrap is muted
    by the first cosmetic edit and then protects nothing."""
    body = [f"  RULE {i}: a load-bearing   sentence\n      of the core." for i in range(27)]
    _write_doctrine(core._ROOT, body=body)
    assert _verify(monkeypatch) == 0


def test_appending_a_duty_outside_the_block_passes(sealed, monkeypatch):
    """The doctrine grows every week by design. If ordinary appends breached the seal it would be
    red daily and switched off (L1.43), so the seal must cover the block and nothing else."""
    path = core._ROOT / core._DOCTRINE_REL
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\nNEW DUTY (2026-08-12): every organ now does one more thing.\n")
    assert _verify(monkeypatch) == 0


def test_deleting_the_markers_fails(sealed, monkeypatch, capsys):
    """Deletion is the cheapest attack on a delimiter-scoped seal: no block, no mismatch."""
    path = core._ROOT / core._DOCTRINE_REL
    path.write_text(path.read_text("utf-8").replace(core._DOCTRINE_CLOSE, "-- end --"), "utf-8")
    assert _verify(monkeypatch) == 1
    assert "markers are not exactly one pair" in capsys.readouterr().out


def test_gutted_block_is_refused_rather_than_sealed(sealed, monkeypatch, capsys):
    """A block emptied to two lines hashes perfectly well. Sealing it would bless the gutting --
    a verdict over an empty population is vacuous, never a pass (L1.57)."""
    _write_doctrine(core._ROOT, body=["  RULE 0: only this survives.", "  RULE 1: and this."])
    assert _verify(monkeypatch) == 1
    assert "has been gutted" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py", "--reseal"])
    assert core.main() == 2
    assert "REFUSING TO SEAL" in capsys.readouterr().out


def test_missing_doctrine_seal_fails_and_names_the_door(sealed, monkeypatch, capsys):
    """The state every checkout was in before R0392: block present, seal absent, fence green."""
    _, lock = sealed
    payload = json.loads(lock.read_text("utf-8"))
    payload.pop("doctrine")
    lock.write_text(json.dumps(payload), "utf-8")
    assert _verify(monkeypatch) == 1
    out = capsys.readouterr().out
    assert "no seal" in out and "--seal-doctrine" in out


def test_seal_doctrine_cannot_launder_a_core_edit(sealed, monkeypatch, capsys):
    """THE RESEAL TRAP, closed by construction. --reseal rewrites every digest, so reaching for it
    to pick up a new artifact would bless any drift it was not aiming at. --seal-doctrine verifies
    the existing seal FIRST and refuses, so it can never be the instrument that launders an edit
    to a rail."""
    const, lock = sealed
    payload = json.loads(lock.read_text("utf-8"))
    payload.pop("doctrine")
    lock.write_text(json.dumps(payload), "utf-8")
    const.write_text(const.read_text("utf-8").replace("<=2%", "<=20%"), "utf-8")
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py", "--seal-doctrine"])
    assert core.main() == 2
    assert "does not verify" in capsys.readouterr().out
    assert "doctrine" not in json.loads(lock.read_text("utf-8")), "no seal may be written"
    assert "<=20%" in const.read_text("utf-8"), "and nothing may be auto-reverted"


def test_seal_doctrine_refuses_to_rebaseline_a_sealed_block(sealed, monkeypatch, capsys):
    """Establishing a FIRST baseline is a different act from accepting a CHANGED one. Only the
    first is available to the organism; the second stays a principal act via --reseal."""
    body = [f"  RULE {i}: rewritten wholesale." for i in range(27)]
    _write_doctrine(core._ROOT, body=body)
    monkeypatch.setattr("sys.argv", ["check_constitution_core.py", "--seal-doctrine"])
    assert core.main() == 2
    assert "PRINCIPAL action" in capsys.readouterr().out
    assert _verify(monkeypatch) == 1, "the edit must still be reported"


def test_real_injected_doctrine_is_sealed_and_intact():
    """The live artifact. The block every organ on this desk is running on right now."""
    doctrine, errors = core.doctrine_current()
    assert errors == []
    assert doctrine is not None and int(str(doctrine["lines"])) >= core._DOCTRINE_MIN_LINES
    lock = json.loads(core._LOCK.read_text("utf-8"))
    sealed = lock.get("doctrine") or {}
    # On the HASH, deliberately -- see the comparison site. Asserting dict equality here would
    # re-introduce the line-count vote through the test suite's back door.
    assert sealed.get("sha256") == doctrine["sha256"], "the injected core has drifted from its seal"


def test_the_sealed_block_is_the_one_that_gets_injected():
    """The seal is only worth what it covers. If `brain_env.sh` stopped reading this file, or the
    markers moved to a different one, the fence would go on verifying a block nobody injects --
    green, and guarding nothing. Ties the sealed text to the spawn path."""
    env = (core._ROOT / "ops/brain_env.sh").read_text("utf-8")
    assert core._DOCTRINE_REL.as_posix() in env, "the sealed file is no longer the injected one"
    doctrine, errors = core.doctrine_current()
    assert errors == [] and doctrine is not None
