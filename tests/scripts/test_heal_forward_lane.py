from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "heal_forward_lane", ROOT / "scripts" / "heal_forward_lane.py"
)
assert SPEC and SPEC.loader
healer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(healer)


def test_error_is_live_when_another_sleeve_ran_later() -> None:
    error = datetime.now(UTC)
    row = {
        "at": error.isoformat(),
        "last_attempt_at": error.isoformat(),
    }
    assert healer._error_is_stale(row) is False


def test_error_is_stale_only_after_the_same_sleeve_is_retried() -> None:
    error = datetime.now(UTC)
    row = {
        "at": error.isoformat(),
        "last_attempt_at": (error + timedelta(seconds=1)).isoformat(),
    }
    assert healer._error_is_stale(row) is True


def test_carry_state_is_permanently_watched() -> None:
    source = (ROOT / "scripts" / "check_desk_module_drift.py").read_text("utf-8")
    assert '"desks/mt5/research/carry_state.py"' in source
