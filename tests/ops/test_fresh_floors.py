"""R0159 content floors: a fresh-but-EMPTY artifact (zero rows, truncated write) must fail the
freshness gate exactly like a stale one -- the silent-empty failure is the class libs.ops.fresh
exists to prevent, and a young mtime on an empty payload is that failure wearing the age gate as
camouflage.

Every test runs against a tmp root (QUANT_FRESH_ROOT) so the production registry is never
polluted, mirroring tests/governance/test_freshness_fence.py."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from libs.ops.fresh import REGISTRY_REL, StaleRead, read_fresh

_REPO = Path(__file__).resolve().parent.parent.parent


def _write(root: Path, rel: str, obj, *, mtime_ago_s: float | None = None) -> Path:
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


# ------------------------------- backward compatibility ---------------------------------------

def test_no_floor_is_the_default_and_empty_stays_fresh(froot):
    """PIN: until a caller opts in, nothing changes -- an empty payload with a young mtime still
    reads fresh, and its contract line carries no floor keys."""
    _write(froot, "data/x.json", {})
    fr = read_fresh("data/x.json", 1.0, caller="t.nofloor", root=froot)
    assert fr.fresh and fr.data == {}
    evs = _registry_events(froot)
    assert [e["event"] for e in evs] == ["contract"]
    assert "min_rows" not in evs[0] and "min_bytes" not in evs[0]


# ------------------------------- min_rows -----------------------------------------------------

def test_min_rows_refuses_fresh_but_empty_list(froot):
    """The R0159 instance itself: zero rows, young mtime -- passes the age gate, must not pass
    the floor. Same failure path as stale: fresh=False, data still returned (fallback), and a
    stale_read event recorded."""
    _write(froot, "data/rows.json", [])
    fr = read_fresh("data/rows.json", 1.0, caller="t.rows0", min_rows=1, root=froot)
    assert not fr.fresh and fr.data == []
    assert "EMPTY" in fr.why and "min_rows=1" in fr.why and "0 row(s)" in fr.why
    assert {"contract", "stale_read"} == {e["event"] for e in _registry_events(froot)}


def test_min_rows_met_stays_fresh_for_list_and_dict(froot):
    _write(froot, "data/l.json", [1, 2, 3])
    _write(froot, "data/d.json", {"a": 1})
    assert read_fresh("data/l.json", 1.0, caller="t.l", min_rows=3, root=froot).fresh
    assert read_fresh("data/d.json", 1.0, caller="t.d", min_rows=1, root=froot).fresh


def test_min_rows_refuses_empty_dict(froot):
    """{} is the truncated-write shape every opted-in executor artifact can present."""
    _write(froot, "data/d.json", {})
    fr = read_fresh("data/d.json", 1.0, caller="t.d0", min_rows=1, root=froot)
    assert not fr.fresh and "min_rows=1" in fr.why


def test_min_rows_uncountable_payload_counts_as_failed(froot):
    """A scalar payload cannot satisfy a rows contract; unverifiable is FAILED, never a pass --
    the same never-weaken direction as the rest of the module."""
    p = froot / "data/n.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("42", "utf-8")
    fr = read_fresh("data/n.json", 1.0, caller="t.scalar", min_rows=1, root=froot)
    assert not fr.fresh and "uncountable int payload" in fr.why


# ------------------------------- min_bytes ----------------------------------------------------

def test_min_bytes_refuses_truncated_write_and_names_observed_size(froot):
    p = _write(froot, "data/b.json", {"v": 1})
    size = p.stat().st_size
    fr = read_fresh("data/b.json", 1.0, caller="t.bytes", min_bytes=4096, root=froot)
    assert not fr.fresh and f"observed {size}B" in fr.why and "min_bytes=4096" in fr.why
    assert "stale_read" in {e["event"] for e in _registry_events(froot)}
    ok = read_fresh("data/b.json", 1.0, caller="t.bytes2", min_bytes=size, root=froot)
    assert ok.fresh


# ------------------------------- refusal semantics --------------------------------------------

def test_floor_violation_raises_under_strict(froot):
    """mode='strict' treats an empty input exactly like a frozen one: worse than no input."""
    _write(froot, "data/rows.json", [])
    with pytest.raises(StaleRead, match="min_rows=1"):
        read_fresh("data/rows.json", 1.0, caller="t.strict", min_rows=1,
                   mode="strict", root=froot)


def test_floors_never_grant_freshness_to_a_stale_read(froot):
    """NEVER-WEAKEN PIN: a floor can only remove freshness. A stale artifact with satisfied
    floors is still stale, and a stale+empty artifact refuses as STALE (the age refusal
    stands; the floor never rewrites an existing refusal into a different one)."""
    _write(froot, "data/full.json", [1, 2, 3], mtime_ago_s=10 * 3600)
    fr = read_fresh("data/full.json", 1.0, caller="t.stalefull", min_rows=1, root=froot)
    assert not fr.fresh and fr.why.startswith("STALE")
    _write(froot, "data/empty.json", [], mtime_ago_s=10 * 3600)
    fr2 = read_fresh("data/empty.json", 1.0, caller="t.staleempty", min_rows=1, root=froot)
    assert not fr2.fresh and fr2.why.startswith("STALE")


def test_state_kind_floor_applies_to_the_payload_not_the_guardian(froot):
    """kind='state' freshness comes from the guardian; the CONTENT floor still guards the state
    payload itself -- a live guardian must not launder an empty state file."""
    _write(froot, "data/stage.json", {}, mtime_ago_s=400 * 3600)   # empty, legitimately old
    _write(froot, "data/guard.json", {"ok": True})                 # guardian alive
    fr = read_fresh("data/stage.json", 1.0, kind="state", guardian="data/guard.json",
                    caller="t.state0", min_rows=1, root=froot)
    assert not fr.fresh and "min_rows=1" in fr.why
    _write(froot, "data/stage.json", {"stage": "S1"}, mtime_ago_s=400 * 3600)
    fr2 = read_fresh("data/stage.json", 1.0, kind="state", guardian="data/guard.json",
                     caller="t.state1", min_rows=1, root=froot)
    assert fr2.fresh and fr2.data == {"stage": "S1"}


def test_declared_floors_join_the_contract_line(froot):
    """The self-building registry carries the WHOLE declared contract, floors included, so the
    who-consumes-what edge list stays honest for opted-in read sites."""
    _write(froot, "data/x.json", {"a": 1})
    read_fresh("data/x.json", 1.0, caller="t.reg", min_rows=1, min_bytes=2, root=froot)
    c = next(e for e in _registry_events(froot) if e["event"] == "contract")
    assert c["min_rows"] == 1 and c["min_bytes"] == 2


# ------------------------------- executor opt-ins (R0159) -------------------------------------

def test_executor_optin_wiring_present_in_source():
    """Fails if an R0159 floor is deleted from an opted-in executor read site (the L1.41
    remove-the-wiring-and-go-red standard, same as the fence's _WIRED check)."""
    src = (_REPO / "scripts/run_cashcarry_executor.py").read_text("utf-8")
    assert src.count("min_rows=1") >= 3, "executor R0159 floor opt-ins reduced below 3"
    for caller in ("_rt_bps", "_structurally_bleeding", "_refresh_guard"):
        assert f"run_cashcarry_executor.{caller}" in src


def test_executor_rt_bps_empty_model_refused_and_recorded(froot):
    """End-to-end through the opted-in call site: a fresh-but-empty cost model must not pass
    silently. The returned cost is the pessimistic default exactly as before (KeyError branch
    unchanged -- no gate weakened), and the read now leaves a stale_read record."""
    import scripts.run_cashcarry_executor as ex
    _write(froot, "data/cost_model.json", {})                      # truncated write, young mtime
    assert ex._rt_bps("CHEAP") == ex._DEFAULT_RT_BPS
    evs = _registry_events(froot)
    assert any(e["event"] == "stale_read"
               and e["caller"] == "run_cashcarry_executor._rt_bps" for e in evs)
    model = {"symbols": {"CHEAP": {"pair": {"500": {"pair_roundtrip_bps": 5.0}}}}}
    _write(froot, "data/cost_model.json", model)                   # healthy model, floor met
    assert ex._rt_bps("CHEAP") == 5.0


def test_executor_empty_guard_stays_neutral_and_is_recorded(froot):
    """A truncated live_guard.json ({}) used to steer the tick at full size silently. The
    decision is unchanged (neutral: full size, takers allowed -- the documented fail-open
    direction), but the empty read is now loud."""
    import scripts.run_cashcarry_executor as ex
    _write(froot, "data/live_guard.json", {})
    ex._refresh_guard()
    assert ex._GUARD == {"size_frac": 1.0, "limit_only": False}
    assert any(e["event"] == "stale_read"
               and e["caller"] == "run_cashcarry_executor._refresh_guard"
               for e in _registry_events(froot))
    _write(froot, "data/live_guard.json",
           {"effective_size_fraction": 0.5, "canary": {"mode": "limit_only"}})
    ex._refresh_guard()                                            # healthy guard still consumed
    assert ex._GUARD == {"size_frac": 0.5, "limit_only": True}
