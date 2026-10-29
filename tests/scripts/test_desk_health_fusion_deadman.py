"""check_desk_health reads the Fusion ruin rail's stamp: RED when stale or LIVE-but-unarmed.

Box 2026-10-29: MT5-FusionDeadman exited 1 on a log write and MT5-FusionDeadmanLive.log had been
empty since 10-22; nothing reported whether data/fusion_deadman_state.json was still advancing.
The limit is 3 missed 5-minute passes (900 s), the gateway's own gate.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "desks" / "mt5" / "scripts" / "check_desk_health.py"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


@pytest.fixture
def dh() -> Any:
    spec = importlib.util.spec_from_file_location("_quant_desk_health_fdm", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._FINDINGS.clear()
    return mod


def _stamp(tmp_path: Path, age_s: float, mode: str = "LIVE", armed: Any = None) -> Path:
    p = tmp_path / "fusion_deadman_state.json"
    doc = {"checked_at": (NOW - timedelta(seconds=age_s)).isoformat(timespec="seconds"),
           "mode": mode, "would": {"action": "NOTHING"},
           "armed": {"principal": True} if armed is None else armed}
    p.write_text(json.dumps(doc), "utf-8")
    return p


def _levels(dh) -> list[str]:
    return [f["level"] for f in dh._FINDINGS]


def test_the_limit_is_three_cadences() -> None:
    spec = importlib.util.spec_from_file_location("_dh_const", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.FUSION_DEADMAN_MAX_AGE_S == 3 * mod.FUSION_DEADMAN_CADENCE_S == 900.0


def test_a_fresh_armed_live_stamp_is_ok(dh, tmp_path) -> None:
    dh.check_fusion_deadman(_stamp(tmp_path, 120), now=NOW)
    assert _levels(dh) == ["OK"]


def test_a_fresh_dry_run_stamp_is_ok(dh, tmp_path) -> None:
    dh.check_fusion_deadman(_stamp(tmp_path, 120, "DRY-RUN", {"principal": False}), now=NOW)
    assert _levels(dh) == ["OK"]


@pytest.mark.parametrize("mode", ["LIVE", "DRY-RUN"])
def test_a_stamp_older_than_three_passes_is_a_problem(dh, tmp_path, mode) -> None:
    dh.check_fusion_deadman(_stamp(tmp_path, 901, mode), now=NOW)
    assert _levels(dh) == ["PROBLEM"]
    assert "STOPPED" in dh._FINDINGS[0]["message"]


@pytest.mark.parametrize("armed", [{"principal": False}, False, {}, None, "yes"])
def test_live_but_not_armed_is_a_problem(dh, tmp_path, armed) -> None:
    p = _stamp(tmp_path, 60, "LIVE", armed if armed is not None else {"principal": None})
    dh.check_fusion_deadman(p, now=NOW)
    assert _levels(dh) == ["PROBLEM"]
    assert "armed is false" in dh._FINDINGS[0]["message"]


def test_live_with_armed_true_bool_is_ok(dh, tmp_path) -> None:
    dh.check_fusion_deadman(_stamp(tmp_path, 60, "LIVE", True), now=NOW)
    assert _levels(dh) == ["OK"]


def test_absent_is_a_problem_unreadable_is_unknown_undatable_is_a_problem(dh, tmp_path) -> None:
    dh.check_fusion_deadman(tmp_path / "absent.json", now=NOW)
    bad = tmp_path / "bad.json"
    bad.write_text("{torn", "utf-8")
    dh.check_fusion_deadman(bad, now=NOW)
    naive = tmp_path / "naive.json"
    naive.write_text(json.dumps({"checked_at": "2026-10-29T11:59:00", "mode": "DRY-RUN"}), "utf-8")
    dh.check_fusion_deadman(naive, now=NOW)
    assert _levels(dh) == ["PROBLEM", "UNKNOWN", "PROBLEM"]


def test_main_runs_the_check() -> None:
    src = SCRIPT.read_text("utf-8")
    assert "    check_fusion_deadman()\n" in src[src.index("def main("):]
