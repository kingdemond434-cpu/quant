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


def test_a_future_stamp_is_unmeasured_not_fresh(tmp_path: Path) -> None:
    rep = fence.build(_desk(tmp_path, -24 * 30, 1, 1), NOW)
    assert rep["artifacts"][0]["status"] == "UNMEASURED" and rep["status"] == "RED"
    assert fence.build(_desk(tmp_path, -0.02, 1, 1), NOW)["status"] == "GREEN"   # clock skew


def test_the_triangle_is_red_after_one_missed_hourly_cycle(tmp_path: Path) -> None:
    assert fence.build(_desk(tmp_path, 1, 1, 1.9), NOW)["status"] == "GREEN"
    assert fence.build(_desk(tmp_path, 1, 1, 2.5), NOW)["status"] == "RED"


def test_the_watchdog_escalating_is_not_the_watchdog_crashing() -> None:
    spec = importlib.util.spec_from_file_location("never_stale_x", ROOT / "ops" / "never_stale.py")
    assert spec is not None and spec.loader is not None
    ns = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ns)
    assert ns.ESCALATED not in (0, 1)
    assert ("MT5-NeverStale", ns.ESCALATED) in ns.TASK_DIAGNOSIS
    assert ("MT5-NeverStale", 1) in ns.TASK_DIAGNOSIS


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


_RUN = r"python|%PY%|\bscp\b|powershell|\bcall\s+\S+\.(cmd|bat)\b|\.exe\b"
_SUCCESS = (r"^exit(\s*/b)?\s+0\s*$", r"^cmd\s*/c\s*exit\s*(/b\s*)?0\s*$",
            r"^\(call\s*\)\s*$")
_CHECKED = r"errorlevel|\|\||&&"


def masked_steps(text: str) -> list[str]:
    """The steps a batch runner can lose: when its LAST executable line is a literal success
    (`exit /b 0`, `exit 0`, `cmd /c exit 0`, `(call )`), every step that runs something must be
    followed by an errorlevel check or capture (or chained with `||` / `&&`) before the next step.
    A guard `exit /b 2` earlier does not save an unchecked step later. Returns the unchecked steps
    ([] = honest). A runner whose last line is not a literal success returns its real code."""
    import re
    code = [ln.strip() for ln in text.splitlines()
            if ln.strip() and not re.match(r"^(rem\b|::|@echo\b|echo\b)", ln.strip(), re.I)]
    if not code or not any(re.search(p, code[-1], re.I) for p in _SUCCESS):
        return []
    bad: list[str] = []
    for i, ln in enumerate(code[:-1]):
        if (not re.search(_RUN, ln, re.I) or re.search(_CHECKED, ln, re.I)
                or re.match(r'^(set\b|if\b.*\bset\s+")', ln, re.I)):
            continue
        nxt = code[i + 1:-1]
        upto = next((k for k, x in enumerate(nxt) if re.search(_RUN, x, re.I)
                     and not re.match(r'^(set\b|if\b.*\bset\s+")', x, re.I)), len(nxt))
        if not any(re.search(_CHECKED, x, re.I) for x in nxt[:upto]):
            bad.append(ln)
    return bad


def test_the_masked_step_reader_catches_the_audited_shapes() -> None:
    assert masked_steps('"%PY%" a.py\nexit /b 0') == ['"%PY%" a.py']
    assert masked_steps('"%PY%" a.py\nif errorlevel 1 exit /b 2\n"%PY%" b.py\nexit /b 0') \
        == ['"%PY%" b.py']
    for tail in ("exit 0", "cmd /c exit 0", "(call )", "EXIT /B 0"):
        assert masked_steps(f'"%PY%" a.py\n{tail}'), tail
    assert masked_steps("call other.cmd\nexit /b 0") == ["call other.cmd"]
    assert masked_steps('"%PY%" a.py\nexit /b %ERRORLEVEL%') == []
    assert masked_steps('"%PY%" a.py\nset "RC=%ERRORLEVEL%"\nexit /b 0') == []
    assert masked_steps('"%PY%" a.py || exit /b 1\nexit /b 0') == []
    assert masked_steps('set "PY=C:\\python.exe"\nexit /b 0') == []


def test_no_scheduled_runner_hard_codes_success() -> None:
    """A runner that ends in a literal success while a step's failure goes unchecked reports
    success whatever it ran (2026-10-14: twelve did, MT5-CostState among them). Batch files (.cmd
    and .bat) are read step by step; a PowerShell runner may not END in a bare `exit 0` without
    ever reading `$LASTEXITCODE`."""
    import re
    roots = ("ops", "desks/mt5/ops", "desks/mt5/scripts")
    masked: dict[str, list[str]] = {}
    for root in roots:
        for p in sorted((ROOT / root).iterdir()):
            text = p.read_text("utf-8", errors="replace") if p.is_file() else ""
            if p.suffix.lower() in (".cmd", ".bat"):
                bad = masked_steps(text)
            elif p.suffix.lower() == ".ps1":
                code = [ln.strip() for ln in text.splitlines()
                        if ln.strip() and not ln.strip().startswith("#")]
                bad = (["exit 0 without $LASTEXITCODE"]
                       if code and re.fullmatch(r"exit\s+0", code[-1], re.I)
                       and re.search(_RUN, text, re.I)
                       and not re.search(r"\$LASTEXITCODE|\$\?", text) else [])
            else:
                continue
            if bad:
                masked[str(p.relative_to(ROOT))] = bad
    assert masked == {}, f"runners that can report success over a failed step: {masked}"
