"""The suite's own write fence (GAP 113), pinned in BOTH directions.

The direction that matters most is the silent one: `changed` must return nothing when nothing
changed. A fence that fires on a clean tree gets disabled within a day, and then the defect it was
built for -- a test run rewriting a ratchet downward -- comes back with the alarm already off.
"""

from __future__ import annotations

from pathlib import Path

from libs.ops.protected_artifacts import PROTECTED, changed, restore, snapshot


def _tree(root: Path, rels: dict[str, str]) -> None:
    for rel, body in rels.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, "utf-8")


def test_SILENT_WHEN_NOTHING_CHANGED(tmp_path: Path) -> None:
    _tree(tmp_path, dict.fromkeys(PROTECTED, "x"))
    assert changed(tmp_path, snapshot(tmp_path)) == []


def test_A_REWRITE_IS_CAUGHT_AND_PUT_BACK(tmp_path: Path) -> None:
    rel = "docs/research/next_law_number.txt"
    _tree(tmp_path, {rel: "60\n"})
    snap = snapshot(tmp_path)
    # exactly the measured regression: an allocator recomputed DOWNWARD from a partial view
    (tmp_path / rel).write_text("43\n", "utf-8")

    assert changed(tmp_path, snap) == [rel]
    restore(tmp_path, rel, snap)
    assert (tmp_path / rel).read_text("utf-8") == "60\n"
    assert changed(tmp_path, snap) == []


def test_IDENTICAL_BYTES_ARE_NOT_A_VIOLATION(tmp_path: Path) -> None:
    """Content, never mtime. An organ that rewrote a file with the same bytes changed nothing,
    and failing a suite on a touched mtime teaches people the fence cries wolf."""
    rel = "docs/graveyard.md"
    _tree(tmp_path, {rel: "dead things\n"})
    snap = snapshot(tmp_path)
    (tmp_path / rel).write_text("dead things\n", "utf-8")
    assert changed(tmp_path, snap) == []


def test_CREATING_A_PROTECTED_FILE_IS_ALSO_A_VIOLATION(tmp_path: Path) -> None:
    """Absent-then-present is the same defect wearing different clothes: the next commit picks up
    a tracked file nobody wrote on purpose, carrying whatever a fixture happened to contain."""
    rel = "docs/research/COVERAGE_RATCHET.json"
    snap = snapshot(tmp_path)                      # nothing exists yet
    assert snap[rel] is None

    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text('{"repo": 0.10}', "utf-8")
    assert changed(tmp_path, snap) == [rel]

    restore(tmp_path, rel, snap)
    assert not (tmp_path / rel).exists()


def test_DELETION_IS_A_VIOLATION_AND_IS_UNDONE(tmp_path: Path) -> None:
    rel = "ops/principal_doctrine.txt"
    _tree(tmp_path, {rel: "the whole doctrine\n"})
    snap = snapshot(tmp_path)
    (tmp_path / rel).unlink()

    assert changed(tmp_path, snap) == [rel]
    restore(tmp_path, rel, snap)
    assert (tmp_path / rel).read_text("utf-8") == "the whole doctrine\n"


def test_EVERY_PROTECTED_PATH_STATES_WHY(tmp_path: Path) -> None:
    """The reason is what the failure prints. A guard that fires without saying what was lost is
    a guard the next person in a hurry switches off."""
    for rel, why in PROTECTED.items():
        assert why.strip(), f"{rel} is protected without a stated reason"
        assert len(why) > 40, f"{rel}'s reason is too thin to act on: {why!r}"


def test_THE_THREE_MEASURED_REGRESSIONS_ARE_COVERED() -> None:
    """The files GAP 113 was opened on. Pinned by name so a future edit to the protected set
    cannot quietly drop the exact cases that produced the law."""
    for rel in ("docs/research/next_law_number.txt",
                "ops/principal_doctrine.txt",
                "docs/research/trade_forensics_latest.json"):
        assert rel in PROTECTED
