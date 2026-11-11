"""check_box_tasks recognises every real task-name shape, and still ignores prose.

`MT5-[A-Z][a-z]...` missed an acronym lead (`MT5-FTMOFollow`) and a digit inside
(`MT5-E8WindowGuard`), so a future reference to either with no manifest line would have
slipped past the DR floor unseen.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_box_tasks as cbt  # noqa: E402


def _names(text: str) -> set[str]:
    return set(cbt._TASK_NAME.findall(text))


def test_acronym_and_digit_task_names_are_recognised() -> None:
    text = 'Start-ScheduledTask MT5-FTMOFollow; Start-ScheduledTask "MT5-E8WindowGuard"'
    assert _names(text) == {"MT5-FTMOFollow", "MT5-E8WindowGuard"}


def test_plain_camelcase_names_still_match_whole() -> None:
    assert _names("MT5-Gauntlet MT5-AdoptRelease MT5-QQuantShadow") == {
        "MT5-Gauntlet", "MT5-AdoptRelease", "MT5-QQuantShadow"}


def test_prose_and_all_caps_are_not_task_names() -> None:
    assert _names("MT5-volume MT5-valid MT5-API MT5-USD") == set()


def test_both_watchers_are_manifested_and_referenced(tmp_path: Path) -> None:
    named = {r.get("name") for r in cbt.manifest_rows()}
    assert {"MT5-FTMOFollow", "MT5-E8WindowGuard"} <= named
    (tmp_path / "heal.ps1").write_text("Start-ScheduledTask MT5-E8WindowGuard\n", "utf-8")
    assert "MT5-E8WindowGuard" in cbt.referenced_tasks(tmp_path)
