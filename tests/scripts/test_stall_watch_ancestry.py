"""Execute only pure watchdog classification functions against synthetic trees."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_shard_wrapper_ancestry_and_true_duplicate_controls():
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell runtime unavailable")
    root = Path(__file__).resolve().parents[2]
    controls = Path(__file__).with_name("stall_watch_ancestry_controls.ps1")
    result = subprocess.run(
        [shell, "-NoProfile", "-File", str(controls),
         "-Source", str(root / "desks/mt5/scripts/stall_watch.ps1")],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "10 pure classification controls passed" in result.stdout
