"""Quota-death catch-up decision rules (libs/ops/organ_catchup.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.organ_catchup import ORGANS, organ_owed, pick_organ

NOW = datetime(2026, 7, 24, 23, 30, tzinfo=UTC)
BRAIN = ORGANS[0]
DATAAXIS = ORGANS[1]


def _write(logdir: Path, name: str, size: int, age_s: float) -> Path:
    p = logdir / name
    p.write_bytes(b"x" * size)
    ts = (NOW - timedelta(seconds=age_s)).timestamp()
    import os

    os.utime(p, (ts, ts))
    return p


def test_stub_death_past_cooldown_is_owed(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260724T1400.log", 51, 4 * 3600)
    assert organ_owed(DATAAXIS, tmp_path, NOW) is True


def test_success_log_today_clears_the_debt(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260724T1400.log", 51, 4 * 3600)
    _write(tmp_path, "dataaxis_20260724T2330.log", 5000, 600)
    assert organ_owed(DATAAXIS, tmp_path, NOW) is False


def test_no_attempt_today_is_not_owed(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260723T1400.log", 51, 30 * 3600)  # yesterday's stub
    assert organ_owed(DATAAXIS, tmp_path, NOW) is False


def test_recent_attempt_respects_cooldown(tmp_path: Path) -> None:
    _write(tmp_path, "dataaxis_20260724T2320.log", 51, 10 * 60)
    assert organ_owed(DATAAXIS, tmp_path, NOW) is False


def test_pick_prioritizes_brain_and_skips_running(tmp_path: Path) -> None:
    _write(tmp_path, "20260724_0845.log", 162, 10 * 3600)
    _write(tmp_path, "dataaxis_20260724T1400.log", 51, 9 * 3600)
    picked = pick_organ(tmp_path, NOW, lambda pat: False)
    assert picked is not None and picked.name == "brain"
    # brain running -> next owed organ is picked instead
    picked2 = pick_organ(tmp_path, NOW, lambda pat: pat == "run_cro_ai.sh")
    assert picked2 is not None and picked2.name == "dataaxis"


def test_fresh_artifact_counts_as_production_despite_stub_log(tmp_path):
    """REGRESSION (2026-07-25): claude writes deliverables via FILE TOOLS, so a SUCCESSFUL dig can
    leave only the shell's ~58-byte start/exit header in its log. Judging success by log size alone
    made max_audit report false 'never fired' defects and made catchup re-fire completed organs
    (frontier_en ran 3x on 07-25 for exactly this reason). A declared artifact written inside the
    interval must count as production."""
    from libs.ops.organ_catchup import OrganSpec, organ_owed

    logdir = tmp_path / "data" / "cro_ai_logs"
    logdir.mkdir(parents=True)
    stub = logdir / f"dataaxis_{NOW.strftime('%Y%m%dT%H%M')}.log"
    stub.write_text("=== dataaxis start ===\n")          # attempted, stub-sized log

    spec = OrganSpec("dataaxis", "ops/run_dataaxis_dig.sh", "dataaxis_*.log", 1500,
                     "run_dataaxis_dig.sh", artifacts=("docs/research/data_axis_watchlist.md",))

    # no artifact yet -> genuinely owed (past cooldown handled by the stub's fresh mtime being old
    # enough is not guaranteed, so assert only the artifact effect below)
    art = tmp_path / "docs" / "research"
    art.mkdir(parents=True)
    (art / "data_axis_watchlist.md").write_text("session note: 2 sources verified\n")

    assert organ_owed(spec, logdir, NOW) is False, (
        "a fresh declared artifact must count as production even when the log is a stub"
    )
