from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "Adopt-Release.ps1"


def test_interrupted_adoption_compares_dirty_paths_without_refreshing_the_index() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    assert '@("hash-object", "--no-filters", "--", $rel)' in body
    assert '@("ls-tree", $target, "--", $rel)' in body
    assert '$batchSize = 100' not in body
    assert "diff --quiet --no-ext-diff $target" not in body
