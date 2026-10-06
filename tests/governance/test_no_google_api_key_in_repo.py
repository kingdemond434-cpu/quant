"""No Google API key literal may sit in any tracked file.

A YouTube Data API key was committed in five desk scripts and three intelligence
artifacts and served from a public repository. Keys are read from the machine
environment (or data/secrets/, which never leaves the box), never from source.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Built by concatenation so this file never matches its own pattern.
KEY_PATTERN = "AI" + "za[0-9A-Za-z_-]{35}"


def test_key_pattern_matches_the_google_key_shape() -> None:
    sample = "AI" + "za" + "A" * 35
    assert re.fullmatch(KEY_PATTERN, sample)
    assert not re.fullmatch(KEY_PATTERN, sample[:-1])


def test_no_tracked_file_carries_a_google_api_key() -> None:
    proc = subprocess.run(
        ["git", "grep", "-I", "-l", "-E", KEY_PATTERN],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    # git grep exits 1 when nothing matches, 0 on a match, >1 on error.
    assert proc.returncode in (0, 1), proc.stderr
    offenders = proc.stdout.split()
    assert not offenders, f"Google API key literal in tracked files: {offenders}"
