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


def test_terminal_clock_is_not_reactivated_by_session_migration(tmp_path: Path) -> None:
    state = {"status": "KILL", "n": 50}
    import pytest
    with pytest.raises(ValueError, match="terminal clock"):
        runtime.ensure("x", {"session": "asia"}, state, ledger=tmp_path / "x.json")
    assert state == {"status": "KILL", "n": 50}


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


def test_prior_promotion_candidate_loses_authority_in_new_window(
        tmp_path: Path, monkeypatch) -> None:
    key = "EURUSD.cross_asset_residual.asia"
    register = tmp_path / "sleeve_registry.json"
    register.write_text(json.dumps({"sleeves": {key: {
        "status": "LIVE", "forward_start": "2026-09-20T00:00:00+00:00",
        "identity": {"family": "cross_asset_residual"}
    }}}), "utf-8")
    monkeypatch.setattr(sleeve_registry, "REGISTRY", register)
    state = {"status": "PROMOTION CANDIDATE", "n": 50,
             "promotion_authority": True, "order_authority": True}
    assert runtime.ensure(key, {"session": "asia"}, state,
                          ledger=tmp_path / "ledger.json",
                          clock_path=tmp_path / "clocks.json",
                          now=datetime(2026, 10, 3, tzinfo=UTC))
    assert state["status"] == "ACTIVE"
    assert state["n"] == 0
    assert state["promotion_authority"] is False
    assert state["order_authority"] is False
