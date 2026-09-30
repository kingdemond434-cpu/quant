"""The Git publisher has no authority to delete market evidence."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"


def test_low_disk_publisher_never_deletes_the_bar_lake() -> None:
    source = SYNC.read_text("utf-8")
    start = source.index("function Free-DiskForGit")
    end = source.index("function Sync-Pull", start)
    body = source[start:end]
    assert "Remove-Item" not in body
    assert "Publisher left every bar/tick/evidence file untouched" in body
