"""The public desk state is projected after every cross-box pull."""
from __future__ import annotations

from pathlib import Path


def test_pull_rebuilds_the_public_projection_after_refreshing_artifacts() -> None:
    script = (Path(__file__).resolve().parents[2] / "ops" / "pull_desk_state.sh").read_text(
        encoding="utf-8"
    )
    assert 'if [ "$ok" = "1" ]; then' in script
    assert ".venv/bin/python scripts/build_zentech_state.py" in script


def test_pull_does_not_publish_unprojected_remote_dashboard() -> None:
    script = (Path(__file__).resolve().parents[2] / 'ops/pull_desk_state.sh').read_text()
    assert 'mv web/desk_state.json.tmp web/desk_state.json' not in script
    assert 'QUANT_DESK_PULL_SNAPSHOT=web/desk_state.json.tmp' in script
    assert script.index('rm -f web/desk_state.json.tmp') > script.index(
        '.venv/bin/python scripts/build_zentech_state.py')
