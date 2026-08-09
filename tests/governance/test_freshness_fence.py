"""L1.44 consumption-time freshness: the helper's contract semantics, the fence's verdicts, and
the wiring-regression checks that fail if a bootstrap contract is deleted.

Every test runs against a tmp root (QUANT_FRESH_ROOT) so the production registry is never
polluted -- a leaked tmp contract would make the real fence report MISSING on a path that never
existed, which is exactly the cry-wolf failure the fence is designed to avoid (L1.43)."""
from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.check_freshness import _WIRED, build_report

from libs.ops.fresh import REGISTRY_REL, FreshRead, StaleRead, read_fresh

_REPO = Path(__file__).resolve().parent.parent.parent


def _write(root: Path, rel: str, obj: dict, *, mtime_ago_s: float | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), "utf-8")
    if mtime_ago_s is not None:
        old = time.time() - mtime_ago_s
        os.utime(p, (old, old))
    return p


def _registry_events(root: Path) -> list[dict]:
    p = root / REGISTRY_REL
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]


@pytest.fixture
def froot(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANT_FRESH_ROOT", str(tmp_path))
    return tmp_path


def test_fresh_young_artifact_and_contract_recorded(froot):
    _write(froot, "data/x.json", {"v": 1})
    fr = read_fresh("data/x.json", 1.0, caller="t.young", root=froot)
    assert isinstance(fr, FreshRead) and fr.fresh and fr.data == {"v": 1}
    evs = _registry_events(froot)
    assert [e["event"] for e in evs] == ["contract"]
    assert evs[0]["caller"] == "t.young" and evs[0]["path"] == "data/x.json"


def test_stale_by_mtime_records_stale_read_and_returns_data(froot):
    _write(froot, "data/x.json", {"v": 1}, mtime_ago_s=10 * 3600)
    fr = read_fresh("data/x.json", 1.0, caller="t.stale", root=froot)
    assert not fr.fresh and fr.data == {"v": 1} and fr.age_h > 9
    assert {"contract", "stale_read"} == {e["event"] for e in _registry_events(froot)}


def test_content_generated_outranks_fresh_mtime(froot):
    # The deploy lie: file rewritten NOW (fresh mtime) but content is a day old. mtime says
    # fresh; the generated stamp must win, in the dangerous direction.
    old = (datetime.now(tz=UTC) - timedelta(hours=24)).isoformat()
    _write(froot, "data/x.json", {"generated": old, "v": 1})
    fr = read_fresh("data/x.json", 1.0, caller="t.deploylie", root=froot)
    assert not fr.fresh and fr.source == "generated" and fr.age_h > 23


def test_state_kind_judged_by_guardian_not_own_age(froot):
    _write(froot, "data/stage.json", {"stage": "S1"}, mtime_ago_s=400 * 3600)  # 400h old state
    _write(froot, "data/guard.json", {"ok": True})                             # guardian alive
    fr = read_fresh("data/stage.json", 1.0, kind="state", guardian="data/guard.json",
                    caller="t.state", root=froot)
    assert fr.fresh and fr.data == {"stage": "S1"}          # old state + live guardian = fresh
    dead = froot / "data/guard.json"
    old = time.time() - 5 * 3600
    os.utime(dead, (old, old))
    fr2 = read_fresh("data/stage.json", 1.0, kind="state", guardian="data/guard.json",
                     caller="t.state2", root=froot)
    assert not fr2.fresh                                     # guardian dead = state untrusted


def test_state_kind_requires_guardian(froot):
    with pytest.raises(ValueError):
        read_fresh("data/x.json", 1.0, kind="state", caller="t.nog", root=froot)


def test_strict_raises_on_stale_and_missing(froot):
    _write(froot, "data/x.json", {"v": 1}, mtime_ago_s=10 * 3600)
    with pytest.raises(StaleRead):
        read_fresh("data/x.json", 1.0, caller="t.strict", mode="strict", root=froot)
    with pytest.raises(StaleRead):
        read_fresh("data/absent.json", 1.0, caller="t.strict2", mode="strict", root=froot)


def test_unreadable_returns_none_and_records(froot):
    p = froot / "data/x.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", "utf-8")
    fr = read_fresh("data/x.json", 1.0, caller="t.corrupt", root=froot)
    assert not fr.fresh and fr.data is None and fr.age_h is None
    assert "unreadable_read" in {e["event"] for e in _registry_events(froot)}


def test_contract_lines_are_throttled(froot):
    _write(froot, "data/x.json", {"v": 1})
    for _ in range(5):
        read_fresh("data/x.json", 1.0, caller="t.throttle", root=froot)
    assert len([e for e in _registry_events(froot) if e["event"] == "contract"]) == 1


def test_relative_path_resolves_against_cwd_not_a_guessed_install(tmp_path, monkeypatch):
    """A relative path means relative to cwd -- the same thing it means to every caller.

    REGRESSION PIN. The first L1.44 helper resolved relatives against an internally-guessed
    install root (/home/quant/quant-platform, else the package parent), which made it the only
    reader in its own process consuming a DIFFERENT install's artifacts than the cwd-relative
    reads sitting beside it in the same file. It broke test_guard_consumes_fresh_artifact
    outright, and it broke the guard's two neighbouring tests INVISIBLY: they kept passing while
    marking against production state instead of their own fixtures. No env var is set here on
    purpose -- pinning the plain-cwd path is the whole point, and pinning it via
    QUANT_FRESH_ROOT would pin the override rather than the default it is overriding."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, "data/x.json", {"v": "from-cwd"})
    fr = read_fresh("data/x.json", 1.0, caller="t.cwd")
    assert fr.fresh and fr.data == {"v": "from-cwd"}
    # and the self-building registry follows the same root, so a chdir'd caller cannot append
    # contract lines to another install's telemetry.
    assert [e["caller"] for e in _registry_events(tmp_path)] == ["t.cwd"]
    assert not (_REPO / REGISTRY_REL).exists() or "t.cwd" not in {
        e.get("caller") for e in _registry_events(_REPO)}


# ------------------------------- fence verdicts -----------------------------------------------

def test_fence_empty_registry_is_unmeasured_never_ok(froot):
    rep = build_report(root=froot)
    assert rep["status"] == "UNMEASURED" and rep["fresh_fraction"] is None


def test_fence_stale_consumed_fails_and_names_caller(froot):
    _write(froot, "data/x.json", {"v": 1}, mtime_ago_s=10 * 3600)
    read_fresh("data/x.json", 1.0, caller="executor.site", root=froot)   # records stale_read
    rep = build_report(root=froot)
    assert rep["status"] == "STALE-CONSUMED"
    assert any("executor.site" in s for s in rep["stale_consumed"])


def test_fence_stale_unread_does_not_fail(froot):
    _write(froot, "data/x.json", {"v": 1})
    read_fresh("data/x.json", 1.0, caller="t.ok", root=froot)            # fresh contract
    old = time.time() - 10 * 3600
    os.utime(froot / "data/x.json", (old, old))                          # goes stale, unread
    # crude but honest: strip the stale_read the contract call would have left -- none exists,
    # since the read happened while fresh. The artifact is now stale with no read since.
    rep = build_report(root=froot)
    assert rep["status"] == "STALE-UNREAD"
    assert rep["by_verdict"]["STALE-UNREAD"] == 1


def test_fence_ok_when_all_fresh(froot):
    _write(froot, "data/x.json", {"v": 1})
    read_fresh("data/x.json", 1.0, caller="t.ok", root=froot)
    rep = build_report(root=froot)
    assert rep["status"] == "OK" and rep["fresh_fraction"] == 1.0


def test_fence_state_contract_judged_by_guardian(froot):
    _write(froot, "data/stage.json", {"stage": "S0"}, mtime_ago_s=400 * 3600)
    _write(froot, "data/guard.json", {"ok": True})
    read_fresh("data/stage.json", 1.0, kind="state", guardian="data/guard.json",
               caller="t.state", root=froot)
    rep = build_report(root=froot)
    assert rep["status"] == "OK"                            # old state file must NOT fire


# ------------------------------- wiring regression --------------------------------------------

def test_bootstrap_wiring_present_in_sources():
    """Fails if a freshness contract is deleted from a bootstrap read site. This is the test the
    L1.41 standard demands: remove the wiring and the suite goes red."""
    for rel, token in _WIRED:
        src = (_REPO / rel).read_text("utf-8", errors="ignore")
        assert token in src, f"{rel} lost its freshness wiring (token {token!r})"
    exec_src = (_REPO / "scripts/run_cashcarry_executor.py").read_text("utf-8")
    assert exec_src.count("read_fresh(") >= 4, "executor bootstrap sites reduced below 4"
    alerts_src = (_REPO / "scripts/run_alerts.py").read_text("utf-8")
    assert "live_guard_dead" in alerts_src and "live_guard_missing" in alerts_src


def test_executor_rt_bps_stale_degrade_only_tightens(froot, monkeypatch):
    """A stale measured cost may only TIGHTEN the entry gate: cheap-stale rises to the default,
    expensive-stale stays expensive. Imports the executor module (test_hedge_and_risk precedent);
    QUANT_FRESH_ROOT keeps its registry writes in tmp."""
    import scripts.run_cashcarry_executor as ex
    model = {"symbols": {
        "CHEAP": {"pair": {"500": {"pair_roundtrip_bps": 5.0}}},
        "DEAR": {"pair": {"500": {"pair_roundtrip_bps": 211.0}}},
    }}
    _write(froot, "data/cost_model.json", model, mtime_ago_s=100 * 3600)   # stale
    assert ex._rt_bps("CHEAP") == ex._DEFAULT_RT_BPS       # stale-cheap may not admit opens
    assert ex._rt_bps("DEAR") == 211.0                     # stale-expensive stays expensive
    _write(froot, "data/cost_model.json", model)                           # fresh again
    assert ex._rt_bps("CHEAP") == 5.0                      # fresh measurement is trusted
    assert ex._rt_bps("MISSING") == ex._DEFAULT_RT_BPS     # unmeasured stays pessimistic
