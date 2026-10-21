"""The cost-state freshness fence and the runner it watches (2026-10-14).

`ops/run_cost_state.cmd` ended `exit /b 0`, so MT5-CostState read green whatever its producers
returned, and origin's cost_surface/carry_state/triangle copies were 21-46 days old with nothing
able to say whether the box's were too. These pin: a stale or absent artifact is RED, a missing
stamp is UNMEASURED (never FRESH), the runner returns its worst step, and the leg is wired.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_cost_state_fresh", ROOT / "scripts" / "check_cost_state_fresh.py")
assert _spec is not None and _spec.loader is not None
fence = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fence)

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)


def _desk(tmp_path: Path, surface_h: float | None, carry_h: float | None,
          tri_h: float | None) -> Path:
    for rel, key, age in (("data/cost_surface.json", "built_at", surface_h),
                          ("data/carry_state.json", "generated_at", carry_h),
                          ("data/tape/triangle_executable.json", "at", tri_h)):
        if age is None:
            continue
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({key: (NOW - timedelta(hours=age)).isoformat()}), "utf-8")
    return tmp_path


def test_all_current_is_green(tmp_path: Path) -> None:
    rep = fence.build(_desk(tmp_path, 5, 20, 1), NOW)
    assert rep["status"] == "GREEN" and rep["n_not_fresh"] == 0


def test_a_stale_cost_surface_is_red(tmp_path: Path) -> None:
    rep = fence.build(_desk(tmp_path, 27, 1, 1), NOW)
    assert rep["status"] == "RED"
    assert rep["not_fresh"] == ["desks/mt5/data/cost_surface.json"]


def test_an_absent_carry_state_is_unmeasured_and_red(tmp_path: Path) -> None:
    rep = fence.build(_desk(tmp_path, 1, None, 1), NOW)
    row = {r["artifact"]: r for r in rep["artifacts"]}["desks/mt5/data/carry_state.json"]
    assert row["status"] == "UNMEASURED" and rep["status"] == "RED"
    assert rep["n_unmeasured"] == 1


def test_an_unstamped_artifact_is_never_fresh(tmp_path: Path) -> None:
    desk = _desk(tmp_path, None, 1, 1)
    (desk / "data" / "cost_surface.json").write_text(json.dumps({"symbols": {}}), "utf-8")
    rep = fence.build(desk, NOW)
    assert rep["artifacts"][0]["status"] == "UNMEASURED"


def test_the_runners_exit_lines_are_read(tmp_path: Path) -> None:
    desk = _desk(tmp_path, 1, 1, 1)
    (desk / "logs").mkdir()
    (desk / "logs" / "MT5-CostState.log").write_text(
        "noise\nMT5-CostState step=carry_state rc=2 at=Tue 04:21\n", "utf-8")
    exits = fence.build(desk, NOW)["runner_exits"]
    assert exits == ["MT5-CostState step=carry_state rc=2 at=Tue 04:21"]


def test_the_runner_returns_its_worst_step_not_a_constant() -> None:
    cmd = (ROOT / "ops" / "run_cost_state.cmd").read_text("utf-8")
    code = [ln.strip() for ln in cmd.splitlines()
            if ln.strip() and not ln.lstrip().startswith("rem")]
    assert "exit /b 0" not in code and "exit /b %WORST%" in code
    assert "MT5-CostState step=" in cmd
    for step in ("cost_surface", "carry_state", "cost_honesty"):
        assert step in cmd


def test_the_leg_is_wired_contracted_and_published() -> None:
    import sys
    for p in (str(ROOT), str(ROOT / "desks" / "mt5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from libs.research import layers
    assert layers.LEG_LAYER["cost_state_fresh"] == "meta"
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"cost_state_fresh": csf' in src and '    "cost_state_fresh",\n' in src
    contracts = json.loads((ROOT / "docs" / "research" / "experiment_contracts.json").read_text())
    assert "cost_state_fresh" in contracts["legs"]
    sync = (ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8")
    assert '"desks/mt5/reports/COST_STATE_FRESHNESS.json"' in sync


def test_no_scheduled_runner_hard_codes_success() -> None:
    """A runner whose every exit is `exit /b 0` reports success whatever it ran (2026-10-14:
    twelve did, MT5-CostState among them). One with no `exit` at all returns its last command's
    code, which is honest; one with only literal-zero exits is not."""
    import re
    roots = ("ops", "desks/mt5/ops", "desks/mt5/scripts")
    masked = []
    for root in roots:
        for p in sorted((ROOT / root).glob("*.cmd")):
            code = [ln.strip() for ln in p.read_text("utf-8", errors="replace").splitlines()
                    if ln.strip() and not ln.strip().lower().startswith("rem")]
            exits = [ln for ln in code if re.search(r"exit\s*/b", ln, re.I)]
            runs = any(re.search(r"python|%PY%|scp|powershell", ln, re.I) for ln in code)
            if runs and exits and all(re.search(r"exit\s*/b\s+0\b", e, re.I) for e in exits):
                masked.append(str(p.relative_to(ROOT)))
    assert masked == [], f"runners that can only ever report success: {masked}"
