"""The public desk state is projected after every cross-box pull."""
from __future__ import annotations

from pathlib import Path


def test_pull_rebuilds_the_public_projection_after_refreshing_artifacts() -> None:
    script = (Path(__file__).resolve().parents[2] / "ops" / "pull_desk_state.sh").read_text(
        encoding="utf-8"
    )
    assert 'if [ "$ok" = "1" ]; then' in script
    assert ".venv/bin/python scripts/build_zentech_state.py" in script
