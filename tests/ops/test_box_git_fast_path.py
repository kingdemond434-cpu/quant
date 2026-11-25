"""The fast path (zuck 2026-11-25 18:53Z; Audit HOLD H1/H2 19:08Z): a CLEARed PR waits only on the
kept money gates, risk suites and replay-shadow (10 min cap each); only a pure box defect passes,
a real red or a hang blocks; other pre-merge checks are informational unless
QUANT_FORGE_FULL_GATING=1."""
from __future__ import annotations

from pathlib import Path

from ops.box_git import box_loop

ROOT = Path(__file__).resolve().parents[2]


def test_fast_path_is_the_default_and_one_env_var_restores_full_gating(monkeypatch):
    monkeypatch.delenv(box_loop.FULL_GATING_ENV, raising=False)
    assert box_loop.fast_path()
    monkeypatch.setenv(box_loop.FULL_GATING_ENV, "1")
    assert not box_loop.fast_path()


def test_only_a_pure_box_defect_passes_and_every_real_red_or_hang_blocks(monkeypatch):
    seen = {}

    def fake(cfg, root, base, head, suite_timeout_s=3600):
        seen["t"] = suite_timeout_s
        return fake.result

    monkeypatch.setattr(box_loop, "risk_job", fake)

    def run(why):
        fake.result = (False, why)
        return box_loop.fast_risk(None, Path("."), "b", "h")[0]

    assert run("risk suites rc=2: Could not determine home directory")          # env, no result
    assert seen["t"] == box_loop.FAST_TIMEOUT_S == 600
    assert not run("risk suites rc=2: 1 failed, 40 passed; PermissionError")    # a result line
    assert not run("risk suites rc=1: PermissionError in test setup")           # rc 1
    assert not run("risk suites rc=2: +++ Timeout +++ in money code")           # a hang
    assert not run("risk suites rc=1: 2 failed, 40 passed")                     # a real red
    fake.result = (True, "risk-invariants passed (9 suite file(s))")
    assert box_loop.fast_risk(None, Path("."), "b", "h") == fake.result


def test_replay_shadow_still_runs_capped_on_the_fast_path(monkeypatch):
    seen = {}

    def fake(cfg, base, head, changed, timeout_s=3600):
        seen["t"] = timeout_s
        return False, "replay-shadow rc=1: divergence not declared"

    monkeypatch.setattr(box_loop, "replay_job", fake)
    assert box_loop.fast_replay(None, "b", "h", ["x.py"])[0] is False
    assert seen["t"] == 600


def test_the_merge_gate_needs_the_risk_job_and_replay_shadow_on_the_forge():
    s = (ROOT / ".github/scripts/audit_gate.py").read_text(encoding="utf-8")
    assert 'FULL_GATING_ENV = "QUANT_FORGE_FULL_GATING"' in s
    assert "need = FORGE_REQUIRED" in s
    assert 'FORGE_REQUIRED = ("risk-invariants", "replay-shadow")' in s
    src = (ROOT / "ops/box_git/box_loop.py").read_text(encoding="utf-8")
    i = src.index("def pr_tick")
    body = src[i:src.index("\ndef ", i + 10)]
    assert body.index("audited_clear") < body.index("fast_path()") < body.index("impacted.select")
