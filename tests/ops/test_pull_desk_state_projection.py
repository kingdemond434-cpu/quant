"""The public desk state is projected after every cross-box pull."""
from __future__ import annotations

from pathlib import Path


def test_pull_rebuilds_the_public_projection_after_refreshing_artifacts() -> None:
    script = (Path(__file__).resolve().parents[2] / "ops" / "pull_desk_state.sh").read_text(
        encoding="utf-8"
    )
    assert 'if [ "$ok" = "1" ]; then' in script
    assert "QUANT_DESK_PULL_SNAPSHOT=web/desk_state.json.tmp" in script
    assert ".venv/bin/python scripts/build_zentech_state.py" in script


def test_campaign_docket_is_not_recopied_when_remote_identity_is_unchanged() -> None:
    script = (Path(__file__).resolve().parents[2] / "ops" / "pull_desk_state.sh").read_text(
        encoding="utf-8"
    )
    assert '_docket_meta="${_docket}.remote_meta"' in script
    assert "campaign rows remain on owner" in script
    assert 'scp -pq "$REMOTE:C:/opt/quant/$_docket"' not in script
