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


# ------------------- R0398: a contracted artifact that has never existed ----------------------


def _vanished(froot, rel: str, caller: str) -> None:
    """Contract an artifact while it exists, then let it vanish -- the state that exited 0.

    A consumer that reads an ABSENT path right now records an `unreadable_read`, so the fence
    already calls that STALE-CONSUMED. The hole R0398 names is the quieter one: the contract is
    on the registry, the artifact is gone, and no read is recent -- so no consumer event points
    at it and no producer-side fence has a row for a path nothing ever produced.
    """
    _write(froot, rel, {"v": 1})
    read_fresh(rel, 1.0, caller=caller, root=froot)     # fresh read -> contract, no event
    (froot / rel).unlink()


def test_fence_fails_on_a_contract_whose_artifact_does_not_exist(froot):
    """R0398. MISSING was folded into STALE-UNREAD and exited 0, so a decision-path consumer
    contracted to a path that no longer exists passed the L1.44 fence green -- the exact
    precondition of the L1.55 fabrication (run_live_guard reading data/ramp_state.json, a file
    that has never existed, and publishing the resulting defaults as evaluated conditions)."""
    _write(froot, "data/x.json", {"v": 1})
    read_fresh("data/x.json", 1.0, caller="t.real", root=froot)
    _vanished(froot, "data/never_written.json", "t.phantom")

    rep = build_report(root=froot)

    assert rep["status"] == "MISSING", rep["status"]
    assert rep["by_verdict"]["MISSING"] == 1
    assert rep["missing"] == ["t.phantom <- data/never_written.json"]
    assert "BUILD OR SCHEDULE THE PRODUCER" in rep["next_action"]


def test_missing_outranks_stale_unread(froot):
    """Both present: the absent artifact must not be hidden behind the merely-old one, because
    they carry different repairs (build a producer vs revive one)."""
    _write(froot, "data/stale.json", {"v": 1})
    read_fresh("data/stale.json", 1.0, caller="t.ok", root=froot)
    old = time.time() - 10 * 3600
    os.utime(froot / "data/stale.json", (old, old))      # stale, unread
    _vanished(froot, "data/gone.json", "t.phantom")
    rep = build_report(root=froot)
    assert rep["status"] == "MISSING"
    assert rep["by_verdict"]["STALE-UNREAD"] == 1 and rep["by_verdict"]["MISSING"] == 1


def test_missing_does_not_outrank_stale_consumed(froot):
    """Ladder order is load-bearing in the other direction too: an artifact being CONSUMED while
    frozen is the smoking gun and must not be masked by an absent one elsewhere."""
    _write(froot, "data/stale.json", {"v": 1}, mtime_ago_s=10 * 3600)
    read_fresh("data/stale.json", 1.0, caller="executor.site", root=froot)   # stale_read event
    _vanished(froot, "data/gone.json", "t.phantom")
    assert build_report(root=froot)["status"] == "STALE-CONSUMED"


@pytest.mark.parametrize(("status", "expect_rc"),
                         [("MISSING", 2), ("STALE-CONSUMED", 2), ("UNWIRED", 2),
                          ("UNMEASURED", 2), ("STALE-UNREAD", 0), ("OK", 0)])
def test_exit_code_agrees_with_the_verdict(froot, monkeypatch, status, expect_rc):
    """The verdict and the exit code are two claims and they must agree: a status that never
    fails the gate is a report, not a fence (L1.28a). STALE-UNREAD stays 0 deliberately -- there
    the producer-side fences genuinely do own chasing the dead producer."""
    import scripts.check_freshness as cf

    # n_contracts is part of every real report (see test_unparseable_registry_lines_...), and
    # since R0417 the exit site declares it as the verdict's denominator. It belongs in the
    # fixture for the same reason `status` does: this test asserts the status->exit-code ladder,
    # and a report that scanned nothing is refused for a SEPARATE reason that would mask it.
    canned = {"status": status, "detail": "", "stale_consumed": [], "unwired": [],
              "missing": [], "n_registry_lines_dropped": 0, "n_contracts": 3}
    monkeypatch.setattr(cf, "_ROOT", froot)
    monkeypatch.setattr(cf, "build_report", lambda *a, **k: canned)
    monkeypatch.setattr("sys.argv", ["check_freshness.py"])
    assert cf.main() == expect_rc


def test_unparseable_registry_lines_are_counted_not_hidden(froot):
    """L1.60: a corrupt line may cost one record, but a drop nobody counts makes 'this registry
    was never written' and 'this registry does not parse' byte-identical to the reader."""
    _write(froot, "data/x.json", {"v": 1})
    read_fresh("data/x.json", 1.0, caller="t.ok", root=froot)
    reg = froot / REGISTRY_REL
    reg.write_text(reg.read_text("utf-8") + "{not json\n" + "also not json\n", "utf-8")
    rep = build_report(root=froot)
    assert rep["n_registry_lines_dropped"] == 2
    assert rep["n_contracts"] == 1


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
    # The cash-carry executor (four read_fresh bootstrap sites) and its two live_guard pager rows
    # were RETIRED 2026-09-05 under the MT5 universe mandate: the executor is deleted, and
    # scripts/run_alerts.py records why the pager rows went (they would fire every tick about a
    # size governor for a book that cannot trade). Pinned as retired, so neither comes back
    # half-wired: a revived executor must re-earn its read_fresh sites here.
    assert not (_REPO / "scripts/run_cashcarry_executor.py").exists()
    alerts_src = (_REPO / "scripts/run_alerts.py").read_text("utf-8")
    assert "THE TWO live_guard ALERTS WERE REMOVED 2026-09-05" in alerts_src
    assert '"live_guard_dead"' not in alerts_src and '"live_guard_missing"' not in alerts_src


def test_executor_rt_bps_stale_degrade_only_tightens(froot, monkeypatch):
    """A stale measured cost may only TIGHTEN the entry gate.

    The organ this pinned, `scripts/run_cashcarry_executor._rt_bps`, was RETIRED 2026-09-05 with
    the Binance executors (ops/crontab.manifest "RETIRED 2026-09-05"), so no entry gate reads
    data/cost_model.json any more. What still binds is the contract `_rt_bps` stood on: a stale
    cost file is REPORTED stale (so a caller can only fall back to its pessimistic default),
    never handed back as though it were fresh, and a fresh one is trusted.
    """
    assert not (_REPO / "scripts/run_cashcarry_executor.py").exists(), (
        "the executor is back -- restore the _rt_bps stale-only-tightens test against it")
    model = {"symbols": {"CHEAP": {"pair": {"500": {"pair_roundtrip_bps": 5.0}}}}}
    _write(froot, "data/cost_model.json", model, mtime_ago_s=100 * 3600)   # stale
    assert not read_fresh("data/cost_model.json", 24.0, caller="t.rt_bps", root=froot).fresh
    _write(froot, "data/cost_model.json", model)                           # fresh again
    fr = read_fresh("data/cost_model.json", 24.0, caller="t.rt_bps", root=froot)
    assert fr.fresh and fr.data == model
