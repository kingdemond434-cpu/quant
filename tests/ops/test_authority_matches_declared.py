"""Replay-shadow MATCHES_DECLARED (the Fusion-roster leg, PR A #1156) is judged by the release
authority as AT LEAST CONTROLLER: the replay stands in as passed only when its own report says so,
the authority re-matches it against the BASE's declaration registry for this PR and exact head,
and the base-run trusted-eval and the CONTROLLER veto window still apply. Never AUTO, never PASS."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("cryptography")

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "authority_sandbox_md", ROOT / "ops/release/authority/sandbox.py"
)
assert _spec is not None and _spec.loader is not None
sb_mod = importlib.util.module_from_spec(_spec)
sys.modules["authority_sandbox_md"] = sb_mod
_spec.loader.exec_module(sb_mod)
H1 = sb_mod.H1
AUTO_FILE = "desks/mt5/data/live_sleeve_policy.json"
FLIPS = [["admit", "EURUSD", "EURUSD.asia#rr=1.5_wait_bars=8"], ["refuse", "USDJPY", "u_asia"]]


def _report(flips: list[list[str]] = FLIPS, **kw: Any) -> dict[str, Any]:
    rep = {
        "verdict": "MATCHES_DECLARED",
        "fusion_roster": {"measured": True, "divergence": flips, "declared": "matched"},
        "problems": [f"fusion roster {k} {s} {n}" for k, s, n in flips],
    }
    rep.update(kw)
    return rep


def _row(head: str = H1, pr: int = 41, **kw: Any) -> dict[str, Any]:
    row = {
        "pr": pr,
        "head_sha": head,
        "admit": ["EURUSD.asia#rr=1.5_wait_bars=8"],
        "refuse": [{"name": "u_asia", "missed_growth": "USDJPY asia breakout off Fusion"}],
    }
    row.update(kw)
    return row


@pytest.fixture
def sb(tmp_path: Path) -> Any:
    s = sb_mod.Sandbox(tmp_path, files=(AUTO_FILE,))
    s.ag.REGISTRY_HOLD_H = 24.0
    s.gh.conclusion["replay-shadow"] = "failure"
    s.gh.replay_report = _report()
    s.base_text["ops/release/expected_divergence.json"] = json.dumps({"rows": [_row()]})
    return s


def test_a_declared_divergence_is_cleared_as_controller_never_auto(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    env = json.loads(next(sb.folder.glob("pr41-*-CLEAR-*.json")).read_text())
    st = json.loads(env["statement"])
    assert st["tier"] == "CONTROLLER"
    assert st["evidence"]["replay_declared"]["run"] is not None


def test_the_base_run_trusted_eval_is_still_required(sb: Any) -> None:
    sb.gh.trusted_eval = None
    assert sb.authority()[0] == "WAIT"
    sb.gh.trusted_eval = "failure"
    assert sb.authority()[0] == "FAIL"


def test_the_gate_merges_it_only_after_the_controller_window(sb: Any) -> None:
    assert sb.authority()[0] == "CLEAR"
    sb.gate()
    assert sb.gh.merges() == []
    sb.clock.advance(hours=23)
    sb.gate()
    assert sb.gh.merges() == []
    sb.clock.advance(hours=1, minutes=2)
    sb.gate()
    (m,) = sb.gh.merges()
    assert m["sha"] == H1


@pytest.mark.parametrize(
    "spoil",
    [
        "no_report",
        "not_declared",
        "wrong_head",
        "two_rows",
        "no_missed_growth",
        "extra_flip",
        "other_problem",
        "undeclarable_kind",
        "unmeasured",
        "no_registry",
        "other_job_red",
        "registry_on_head_only",
    ],
)
def test_anything_short_of_an_exact_declared_match_stays_fail(sb: Any, spoil: str) -> None:
    reg = "ops/release/expected_divergence.json"
    if spoil == "no_report":
        sb.gh.replay_report = None
    elif spoil == "not_declared":
        sb.gh.replay_report = _report(verdict="FAIL")
    elif spoil == "wrong_head":
        sb.base_text[reg] = json.dumps({"rows": [_row(head="3" * 40)]})
    elif spoil == "two_rows":
        sb.base_text[reg] = json.dumps({"rows": [_row(), _row()]})
    elif spoil == "no_missed_growth":
        sb.base_text[reg] = json.dumps({"rows": [_row(refuse=[{"name": "u_asia"}])]})
    elif spoil == "extra_flip":
        sb.gh.replay_report = _report([*FLIPS, ["admit", "GBPUSD", "g"]])
    elif spoil == "other_problem":
        rep = _report()
        rep["problems"] = [*rep["problems"], "UNMEASURED money-path change: x.py"]
        sb.gh.replay_report = rep
    elif spoil == "undeclarable_kind":
        sb.gh.replay_report = _report([["zero", "EURUSD", "x"]])
    elif spoil == "unmeasured":
        rep = _report()
        rep["fusion_roster"]["measured"] = False
        sb.gh.replay_report = rep
    elif spoil == "no_registry":
        del sb.base_text[reg]
    elif spoil == "other_job_red":
        sb.gh.conclusion["risk-invariants"] = "failure"
    elif spoil == "registry_on_head_only":  # a PR can never declare its own divergence
        sb.head_text[reg] = sb.base_text.pop(reg)
    assert sb.authority()[0] == "FAIL"
    assert not list(sb.folder.glob("pr41-*-CLEAR-*.json"))


def test_a_green_replay_is_not_raised_to_controller(sb: Any) -> None:
    sb.gh.conclusion["replay-shadow"] = "success"
    sb.gh.trusted_eval = None  # an AUTO PR does not wait on it
    assert sb.authority()[0] == "CLEAR"


def test_the_gate_accepts_controller_for_auto_only_with_a_declared_replay() -> None:
    ag = sb_mod._load("audit_gate", ROOT / ".github" / "scripts" / "audit_gate.py")
    st = {"head_sha": H1, "verdict": "CLEAR", "patch_id": "p", "tier": "CONTROLLER",
          "issued_at": "2026-11-14T00:00:00Z", "evidence": {}}  # fmt: skip
    assert ag.authority_clear([st], H1, "p", "AUTO")[0] is None
    st["evidence"] = {"replay_declared": {"run": 7, "why": "MATCHES_DECLARED"}}
    assert ag.authority_clear([st], H1, "p", "AUTO")[0] is not None
    assert ag.authority_clear([st], H1, "p", "LOW")[0] is not None
    assert ag.authority_clear([{**st, "tier": "AUTO"}], H1, "p", "PROTECTED")[0] is None


def test_newest_run_id_reads_only_genuine_runs() -> None:
    ag = sb_mod._load("audit_gate", ROOT / ".github" / "scripts" / "audit_gate.py")
    runs = [
        {"id": 1, "name": "replay-shadow", "started_at": "2026-11-14T00:00:00Z", "ok": True},
        {"id": 2, "name": "replay-shadow", "started_at": "2026-11-14T01:00:00Z", "ok": True},
        {"id": 3, "name": "replay-shadow", "started_at": "2026-11-14T02:00:00Z", "ok": False},
    ]
    assert ag.newest_run_id(runs, "replay-shadow", lambda r: bool(r["ok"])) == 2
    assert ag.newest_run_id(runs, "quality", lambda r: True) is None
