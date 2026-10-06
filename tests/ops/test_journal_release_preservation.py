"""Evidence classification preserves decisions without admitting controller code drift."""
import re
from pathlib import Path

from libs.ops import protected_artifacts, release


def test_exact_journal_and_lessons_are_state_and_protected() -> None:
    assert release.is_state_path("context/decision_journal.jsonl")
    assert release.is_state_path("docs/desk_lessons.jsonl")
    assert "context/decision_journal.jsonl" in protected_artifacts.PROTECTED
    assert not release.is_state_path("context/DELEGATION_PROTOCOL.md")
    assert not release.is_state_path("context/run_controller.py")


def test_adopter_uses_the_same_exact_evidence_paths() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "desks/mt5/scripts/Adopt-Release.ps1").read_text("utf-8")
    paths = set(re.findall(r'"([^"]+)"',script.split("$StateFiles = @(",1)[1].split(")",1)[0]))
    assert paths == release.STATE_FILES
