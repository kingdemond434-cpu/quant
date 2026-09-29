from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "Adopt-Release.ps1"


def test_interrupted_adoption_compares_dirty_paths_in_batches() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    assert '$batchSize = 100' in body
    assert '@("diff", "--name-only", "--no-ext-diff", $target, "--") + $batch' in body
    assert "diff --quiet --no-ext-diff $target" not in body
