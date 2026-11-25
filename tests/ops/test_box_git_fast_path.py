"""The fast path (zuck 2026-11-25 18:53Z; Audit design check 18:53Z): a CLEARed PR waits only on the
money-path risk suites (10 min cap); an env-classed failure never blocks, a real red does; the
other pre-merge checks are informational unless QUANT_FORGE_FULL_GATING=1."""
from __future__ import annotations

from pathlib import Path

from ops.box_git import box_loop

ROOT = Path(__file__).resolve().parents[2]


def test_fast_path_is_the_default_and_one_env_var_restores_full_gating(monkeypatch):
    monkeypatch.delenv(box_loop.FULL_GATING_ENV, raising=False)
    assert box_loop.fast_path()
    monkeypatch.setenv(box_loop.FULL_GATING_ENV, "1")
    assert not box_loop.fast_path()


def test_env_failures_do_not_block_and_real_reds_do(monkeypatch):
    seen = {}

    def fake(cfg, root, base, head, suite_timeout_s=3600):
        seen["t"] = suite_timeout_s
        return fake.result

    monkeypatch.setattr(box_loop, "risk_job", fake)
    fake.result = (False, "risk suites rc=1: Could not determine home directory")
    ok, why = box_loop.fast_risk(None, Path("."), "b", "h")
    assert ok and "does not block" in why and seen["t"] == box_loop.FAST_RISK_TIMEOUT_S == 600
    fake.result = (False, "risk suites rc=1: 2 failed, 40 passed")
    assert box_loop.fast_risk(None, Path("."), "b", "h") == fake.result
    fake.result = (True, "risk-invariants passed (9 suite file(s))")
    assert box_loop.fast_risk(None, Path("."), "b", "h") == fake.result


def test_the_merge_gate_needs_only_the_risk_job_on_the_forge():
    s = (ROOT / ".github/scripts/audit_gate.py").read_text(encoding="utf-8")
    assert 'FULL_GATING_ENV = "QUANT_FORGE_FULL_GATING"' in s
    assert "need = (RISK_JOB,)" in s
    src = (ROOT / "ops/box_git/box_loop.py").read_text(encoding="utf-8")
    i = src.index("def pr_tick")
    body = src[i:src.index("\ndef ", i + 10)]
    assert body.index("audited_clear") < body.index("fast_path()") < body.index("impacted.select")
