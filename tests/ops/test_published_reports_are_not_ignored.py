"""Every report the box sync publishes must be re-included past `.gitignore`'s `**/reports/*`."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"


def _report_paths() -> list[str]:
    src = SYNC.read_text(encoding="utf-8")
    start = src.index("$reportPaths = @(")
    block = src[start:src.index("\n)", start)]
    return re.findall(r'^\s*"([^"]+)"', block, re.M)


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_every_published_report_is_reincluded() -> None:
    paths = _report_paths()
    assert "desks/mt5/reports/CRO_DUTIES.json" in paths
    out = subprocess.run(["git", "check-ignore", "--no-index", *paths], cwd=ROOT,
                         capture_output=True, text=True, check=False)
    ignored = out.stdout.split()
    assert not ignored, (f"sync_shadow_to_git.ps1 publishes {ignored} but .gitignore ignores "
                         "them, so `git add` skips them and they never reach origin")
