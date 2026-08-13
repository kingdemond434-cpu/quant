"""L1.38 sterile cockpit -- money-path freeze inside launch/first-fills/rail windows only."""
from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.check_change_window import (
    REPAIR_MARKER,
    build_report,
    classify_commits,
    restart_verdict,
    touches_money_path,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _launch(root: Path, days_ago: float, fills: int = 50) -> None:
    (root / "data/moat/execution_tape").mkdir(parents=True, exist_ok=True)
    (root / "data/moat/execution_tape/cashcarry_trades.jsonl").write_text(
        "\n".join('{"x":1}' for _ in range(fills)), "utf-8")
    # R0333: the executor publishes its book state here, not to the phantom cashcarry_state.json.
    (root / "data/cashcarry_positions.json").write_text(
        '{"last_risk_action": "normal", "positions": {}}', "utf-8")
    at = (NOW - timedelta(days=days_ago)).isoformat()
    (root / "data/capital_events.jsonl").write_text(
        json.dumps({"at": at, "kind": "DEPOSIT"}) + "\n", "utf-8")


def test_pre_launch_is_open_even_with_money_path_change(tmp_path):
    rep = build_report(tmp_path, NOW, paths=["libs/execution/binance_live.py"])
    assert rep["status"] == "OPEN"
    assert rep["verdict"] == "ALLOW"          # nothing live can be harmed pre-launch


def test_launch_week_blocks_money_path_improvement(tmp_path):
    _launch(tmp_path, days_ago=2)
    rep = build_report(tmp_path, NOW, paths=["libs/risk/sizing.py"])
    assert rep["status"] == "STERILE"
    assert rep["verdict"] == "BLOCK"
    assert any("GATE0_LAUNCH" in w for w in rep["windows_active"])


def test_research_change_is_allowed_during_the_freeze(tmp_path):
    _launch(tmp_path, days_ago=2)
    rep = build_report(tmp_path, NOW, paths=["scripts/run_deep_sweep.py", "ops/kimi.txt"])
    assert rep["status"] == "STERILE"         # window is live...
    assert rep["verdict"] == "ALLOW"          # ...but a non-money-path change is never blocked


def test_first_fills_window_blocks(tmp_path):
    _launch(tmp_path, days_ago=10, fills=5)   # past launch week, but < 20 fills
    rep = build_report(tmp_path, NOW, paths=["libs/execution/binance_live.py"])
    assert rep["verdict"] == "BLOCK"
    assert any("FIRST_FILLS" in w for w in rep["windows_active"])


def test_rail_breach_window_blocks(tmp_path):
    _launch(tmp_path, days_ago=30, fills=100)
    (tmp_path / "data/cashcarry_positions.json").write_text(
        '{"last_risk_action": "flatten", "positions": {}}', "utf-8")
    rep = build_report(tmp_path, NOW, paths=["scripts/run_cashcarry_executor.py"])
    assert rep["verdict"] == "BLOCK"
    assert any("RAIL_BREACH" in w for w in rep["windows_active"])


def test_settled_book_opens_the_window(tmp_path):
    _launch(tmp_path, days_ago=30, fills=100)  # past launch, plenty of fills, no rail
    rep = build_report(tmp_path, NOW, paths=["libs/execution/binance_live.py"])
    assert rep["status"] == "OPEN"
    assert rep["verdict"] == "ALLOW"


def test_freeze_is_improvements_not_repairs_in_the_law_text():
    src = Path("scripts/check_change_window.py").read_text("utf-8")
    assert "freezes IMPROVEMENTS, never REPAIRS" in src
    doc = Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert "IMPROVEMENTS, NEVER REPAIRS" in doc


def test_money_path_matcher():
    assert touches_money_path(["libs/risk/gate.py"]) == ["libs/risk/gate.py"]
    assert touches_money_path(["docs/research/x.md"]) == []


# --- R0426: the window judged a WINDOW, never a DIFF ------------------------------------------
# L1.38 freezes money-path IMPROVEMENTS and always allows REPAIRS, but the unit of deployment is a
# PROCESS RESTART, not a commit -- so a repair sitting behind a withheld improvement could not be
# shipped without also shipping the improvement, and this fence had no vocabulary for saying which
# pending commits were which. That is the live instance the row was raised on.


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          check=True).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "libs/execution").mkdir(parents=True)
    (r / "scripts").mkdir(parents=True)
    _git(r.parent, "init", "-q", str(r))
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "README").write_text("base\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    return r


def _commit(repo: Path, rel: str, msg: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text((p.read_text() if p.exists() else "") + "x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)


def test_a_money_path_commit_is_an_improvement_unless_it_DECLARES_a_repair(tmp_path):
    repo = _repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "libs/execution/conn.py", "tidy the connector")             # undeclared
    _commit(repo, "libs/execution/conn.py", f"{REPAIR_MARKER} -- futures leg reported a re-base")
    _commit(repo, "scripts/run_deep_sweep.py", "research change")
    kinds = {c["kind"]: c["subject"] for c in classify_commits(base, "HEAD", root=repo)}
    assert set(kinds) == {"IMPROVEMENT", "REPAIR", "NON-MONEY-PATH"}
    assert kinds["IMPROVEMENT"] == "tidy the connector"      # UNDECLARED IS NEVER A REPAIR
    assert kinds["REPAIR"].startswith(REPAIR_MARKER)
    assert kinds["NON-MONEY-PATH"] == "research change"


def test_a_repair_stuck_behind_a_withheld_improvement_is_named(tmp_path):
    """THE LIVE INSTANCE R0426 WAS RAISED ON: restarting to land the repair also lands the
    improvement a prior session deliberately withheld, and nothing could say so."""
    repo = _repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "libs/execution/conn.py", "improve sizing telemetry")       # withheld
    _commit(repo, "libs/execution/conn.py", f"{REPAIR_MARKER} -- net_pnl_basis")
    rv = restart_verdict(base, "HEAD", root=repo, status="STERILE")
    assert rv["verdict"] == "BLOCK"
    assert rv["n_repairs"] == 1 and rv["n_blocking"] == 1
    assert "improve sizing telemetry" in rv["blocking"][0]["subject"]


def test_all_declared_repairs_may_deploy_inside_a_window(tmp_path):
    repo = _repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "libs/execution/conn.py", f"{REPAIR_MARKER} -- a live defect")
    rv = restart_verdict(base, "HEAD", root=repo, status="STERILE")
    assert rv["verdict"] == "ALLOW" and rv["n_repairs"] == 1


def test_no_money_path_commits_is_NOT_reported_as_all_repairs(tmp_path):
    """Two different facts: 'the freeze never applied' vs 'every frozen thing is a repair'."""
    repo = _repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "scripts/run_deep_sweep.py", "research only")
    rv = restart_verdict(base, "HEAD", root=repo, status="STERILE")
    assert rv["verdict"] == "ALLOW"
    assert "touch the money path" in rv["why"] and "declared repairs" not in rv["why"]


def test_an_open_window_never_blocks_a_restart(tmp_path):
    repo = _repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "libs/execution/conn.py", "undeclared money-path change")
    assert restart_verdict(base, "HEAD", root=repo, status="OPEN")["verdict"] == "ALLOW"
