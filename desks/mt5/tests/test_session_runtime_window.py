from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (str(DESK), str(DESK / "research")):
    if path not in sys.path:
        sys.path.insert(0, path)

from research import session_runtime_window as runtime  # noqa: E402
import clock_ledger  # noqa: E402
import sleeve_registry  # noqa: E402


def test_session_correction_opens_new_clock_and_preserves_old_evidence(
        tmp_path: Path, monkeypatch) -> None:
    key = "EURUSD.cross_asset_residual.asia"
    old = "2026-09-20T00:00:00+00:00"
    now = datetime(2026, 10, 3, 0, 0, tzinfo=UTC)
    register = tmp_path / "sleeve_registry.json"
    register.write_text(json.dumps({"sleeves": {key: {
        "status": "LIVE", "forward_start": old, "identity": {"family": "cross_asset_residual"}
    }}}), "utf-8")
    monkeypatch.setattr(sleeve_registry, "REGISTRY", register)
    clocks = tmp_path / "clocks.json"
    clock_ledger.stamp(key, "", old, path=clocks)
    ledger = tmp_path / "ledger_EURUSD_cross_asset_residual_asia.json"
    ledger.write_text('[{"r_multiple":1.2,"phase":"forward"}]', "utf-8")
    state = {"forward_start": old, "n": 1, "cum_r": 1.2, "exp_r": 1.2,
             "status": "ACTIVE", "promotion_authority": True}

    assert runtime.ensure(key, {"session": "asia"}, state, ledger=ledger,
                          clock_path=clocks, now=now)
    assert state["n"] == 0 and state["promotion_authority"] is False
    assert state["forward_start"] == now.isoformat(timespec="seconds")
    archive = Path(state["runtime_windows_before"][0]["archived_ledger"])
    assert json.loads(archive.read_text("utf-8"))[0]["r_multiple"] == 1.2
    reg = json.loads(register.read_text("utf-8"))["sleeves"][key]
    assert reg["forward_start"] == state["forward_start"]
    assert reg["runtime_windows_before"][0]["forward_start"] == old
    assert sleeve_registry.verify(key, {"family": "cross_asset_residual",
                                        "runtime_version": runtime.VERSION}) == []
    assert sleeve_registry.verify(key, {"family": "cross_asset_residual",
                                        "runtime_version": "future-filter-version"}) == [
                                            "runtime_version"]
    entries = json.loads(clocks.read_text("utf-8"))["clocks"]
    assert len(entries) == 2 and sum(not e.get("closed") for e in entries.values()) == 1

    assert not runtime.ensure(key, {"session": "asia"}, state, ledger=ledger,
                              clock_path=clocks, now=now)
    assert len(json.loads(register.read_text("utf-8"))["sleeves"][key]
               ["runtime_windows_before"]) == 1


def test_all_session_does_not_discard_valid_forward_history(tmp_path: Path) -> None:
    state = {"n": 50, "forward_start": "2026-09-20T00:00:00+00:00"}
    assert not runtime.ensure("x", {"session": "all"}, state, ledger=tmp_path / "x.json")
    assert state["n"] == 50


def test_terminal_clock_is_not_reactivated_and_not_frozen(tmp_path: Path) -> None:
    """Every spelling the forward clock calls terminal -- PROMOTED, KILL, KILL_*, PROMOTION
    CANDIDATE -- is neither revived nor aborted (audit 2026-10-06): raising made shadow_forward
    skip the sleeve every pass, and an exact-match tuple reset PROMOTION CANDIDATE and KILL_*
    rows to ACTIVE with n=0."""
    for status in ("KILL", "PROMOTED", "KILL_DD", "PROMOTION CANDIDATE"):
        state = {"status": status, "n": 50, "runtime_version": None}
        assert not runtime.ensure("x", {"session": "asia"}, state, ledger=tmp_path / "x.json")
        assert state["status"] == status and state["n"] == 50
        assert state["runtime_window"]["status"] == "UNMEASURED"
        assert status in state["runtime_window"]["why"]
        assert "forward_start" not in state


def test_version_is_the_same_in_every_process() -> None:
    """The live defect (audit 2026-10-06): `repr` of a comprehension's code object carries a
    memory address, so VERSION differed per process and every session clock restarted every
    pass. Three fresh interpreters with three hash seeds must agree."""
    import os
    import subprocess
    code = ("import sys; sys.path[:0]=['.', 'research']; "
            "import session_runtime_window as s; print(s.VERSION, s.CONTRACT)")
    seen = {subprocess.run([sys.executable, "-c", code], cwd=DESK, capture_output=True,
                           text=True, check=True,
                           env={**os.environ, "PYTHONHASHSEED": str(seed)}).stdout.strip()
            for seed in (1, 2, 3)}
    assert seen == {f"{runtime.VERSION} {runtime.CONTRACT}"}


def _window_registry(tmp_path: Path, monkeypatch, key: str) -> None:
    register = tmp_path / "sleeve_registry.json"
    register.write_text(json.dumps({"sleeves": {key: {
        "status": "LIVE", "forward_start": "2026-09-20T00:00:00+00:00",
        "identity": {"family": "cross_asset_residual"}}}}), "utf-8")
    monkeypatch.setattr(sleeve_registry, "REGISTRY", register)


def test_a_behaviour_change_with_the_same_version_restarts(tmp_path: Path, monkeypatch) -> None:
    """Either trigger restarts: same bytecode name, different outputs, is a new rule."""
    key = "EURUSD.cross_asset_residual.asia"
    _window_registry(tmp_path, monkeypatch, key)
    state = {"status": "ACTIVE", "n": 30, "runtime_version": runtime.VERSION,
             "runtime_contract": "contract-before-change", "forward_start": "2026-09-20"}
    assert runtime.ensure(key, {"session": "asia"}, state, ledger=tmp_path / "l.json",
                          clock_path=tmp_path / "clocks.json",
                          now=datetime(2026, 10, 6, tzinfo=UTC))
    assert state["n"] == 0 and state["runtime_contract"] == runtime.CONTRACT


def test_a_new_version_with_the_same_behaviour_restarts(tmp_path: Path, monkeypatch) -> None:
    key = "EURUSD.cross_asset_residual.asia"
    _window_registry(tmp_path, monkeypatch, key)
    state = {"status": "ACTIVE", "n": 30, "runtime_version": "session-oldbytecode00",
             "runtime_contract": runtime.CONTRACT, "forward_start": "2026-09-20"}
    assert runtime.ensure(key, {"session": "asia"}, state, ledger=tmp_path / "l.json",
                          clock_path=tmp_path / "clocks.json",
                          now=datetime(2026, 10, 6, tzinfo=UTC))
    assert state["runtime_version"] == runtime.VERSION and state["n"] == 0


def test_an_unchanged_window_is_left_alone(tmp_path: Path) -> None:
    state = {"status": "ACTIVE", "n": 30, "runtime_version": runtime.VERSION}
    assert not runtime.ensure("x", {"session": "asia"}, state, ledger=tmp_path / "x.json")
    assert state["n"] == 30 and state["runtime_contract"] == runtime.CONTRACT
    assert not runtime.ensure("x", {"session": "asia"}, state, ledger=tmp_path / "x.json")


def test_the_probe_sees_the_changes_content_alone_missed(monkeypatch) -> None:
    """Each change the audit found counting under a changed rule moves the fingerprint, and a
    spelling the helpers ignore does not."""
    import axis_registry
    from mt5desk import family_call, family_inputs
    before = runtime.contract_fingerprint()
    assert before == runtime.CONTRACT and before.startswith("contract-")
    with monkeypatch.context() as m:
        m.setitem(family_call.SESSIONS, "overlap", (13, 16))         # an added overlap window
        assert runtime.contract_fingerprint() != before
    with monkeypatch.context() as m:
        m.setitem(family_call.SESSIONS, "tokyo", (0, 8))             # an alias the filter learns
        assert runtime.contract_fingerprint() != before
    with monkeypatch.context() as m:
        m.setattr(runtime, "IDENTITY_KEYS",
                  frozenset(family_inputs.IDENTITY_KEYS - {"timeframe"}))
        m.setattr(family_inputs, "IDENTITY_KEYS",
                  frozenset(family_inputs.IDENTITY_KEYS - {"timeframe"}))   # a dropped key
        assert runtime.contract_fingerprint() != before
    with monkeypatch.context() as m:
        orig = family_call.session_filter

        def minute_aware(sigs, session):
            return [g for g in orig(sigs, session)
                    if getattr(getattr(g, "time", None), "minute", 0) == 0]
        m.setattr(runtime, "session_filter", minute_aware)           # :30 bars treated apart
        assert runtime.contract_fingerprint() != before
    with monkeypatch.context() as m:
        m.setitem(axis_registry.SESSION_ALIAS, "brand_new_alias", "asia")
        assert runtime.contract_fingerprint() == before              # ignored by the filter


def test_terminal_registry_refuses_before_opening_new_clock(
        tmp_path: Path, monkeypatch) -> None:
    key = "EURUSD.cross_asset_residual.asia"
    register = tmp_path / "sleeve_registry.json"
    register.write_text(json.dumps({"sleeves": {key: {"status": "RETIRED"}}}), "utf-8")
    monkeypatch.setattr(sleeve_registry, "REGISTRY", register)
    clocks = tmp_path / "clocks.json"
    state = {"status": "ACTIVE", "n": 50}
    import pytest
    with pytest.raises(ValueError, match="terminal registry status"):
        runtime.ensure(key, {"session": "asia"}, state,
                       ledger=tmp_path / "ledger.json", clock_path=clocks)
    assert not clocks.exists()
    assert state == {"status": "ACTIVE", "n": 50}


def test_an_active_row_loses_authority_in_new_window(
        tmp_path: Path, monkeypatch) -> None:
    key = "EURUSD.cross_asset_residual.asia"
    _window_registry(tmp_path, monkeypatch, key)
    state = {"status": "ACTIVE", "n": 50,
             "promotion_authority": True, "order_authority": True}
    assert runtime.ensure(key, {"session": "asia"}, state,
                          ledger=tmp_path / "ledger.json",
                          clock_path=tmp_path / "clocks.json",
                          now=datetime(2026, 10, 3, tzinfo=UTC))
    assert state["status"] == "ACTIVE"
    assert state["n"] == 0
    assert state["promotion_authority"] is False
    assert state["order_authority"] is False
