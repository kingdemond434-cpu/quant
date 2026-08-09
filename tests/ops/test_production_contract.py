from __future__ import annotations

import pytest

from libs.ops.production_contract import (
    accounting_from_execution_tape,
    autonomous_recovery_plan,
    decision_record,
    deterministic_hot_path,
    latency_metrics,
    preflight_contract,
    reality_gap,
    strategy_manifest,
    venue_eligibility,
)


def _manifest() -> dict[str, object]:
    return strategy_manifest(
        {
            "strategy_id": "carry",
            "signal": "s1",
            "allocator": "a1",
            "risk_policy": "locked",
            "execution_policy": "maker-first",
        },
        version="1",
    )


def test_decision_ledger_records_nontrades_with_state() -> None:
    row = decision_record(
        decision_id="d1",
        decision="COST_REJECTED",
        strategy_version="1",
        state_snapshot={"spread": 4},
        rationale="edge below cost",
    )
    assert len(row["record_hash"]) == 64
    with pytest.raises(ValueError):
        decision_record(
            decision_id="d",
            decision="MAYBE",
            strategy_version="1",
            state_snapshot={"x": 1},
            rationale="x",
        )
    with pytest.raises(ValueError):
        decision_record(
            decision_id="d",
            decision="RISK_REJECTED",
            strategy_version="1",
            state_snapshot={},
            rationale="x",
        )


def test_manifest_is_canonical_immutable_and_child_versioned() -> None:
    parent = _manifest()
    child = strategy_manifest(
        parent["specification"], version="2", parent_hash=str(parent["manifest_hash"])
    )
    assert parent["immutable"] is True
    assert child["parent_hash"] == parent["manifest_hash"]
    assert child["manifest_hash"] != parent["manifest_hash"]
    with pytest.raises(ValueError):
        strategy_manifest({"strategy_id": "x"}, version="1")


def test_reality_gap_compares_every_stage_and_preflight_fails_closed() -> None:
    base = {
        "decision_id": "d",
        "signal": 1,
        "decision": "EXECUTED",
        "desired_order": {"qty": 1},
        "fill": 100,
        "cost_bps": 2,
    }
    gap = reality_gap([base], [base], [base | {"fill": 101}])
    assert gap["parity"] == pytest.approx(0.8)
    checks = dict.fromkeys(
        (
            "data_fresh",
            "clock_synchronised",
            "manifest_hash_valid",
            "venue_eligible",
            "auth_valid",
            "reconciled",
            "risk_kernel_valid",
            "journal_writable",
        ),
        True,
    )
    assert preflight_contract(checks)["status"] == "ELIGIBLE"
    assert preflight_contract(checks | {"data_fresh": None})["status"] == "INELIGIBLE"


def test_venue_contract_and_tape_accounting() -> None:
    assert venue_eligibility({"post_only": True}, {"post_only": True})["status"] == "ELIGIBLE"
    assert (
        venue_eligibility({}, {"post_only": {"value": True, "hard": False}})["status"] == "DEGRADED"
    )
    assert venue_eligibility({}, {"post_only": True})["status"] == "INELIGIBLE"
    tape = accounting_from_execution_tape(
        [
            {"event_id": "1", "symbol": "BTC", "side": "BUY", "qty": 2, "price": 10, "fee": 1},
            {"event_id": "2", "symbol": "BTC", "side": "SELL", "qty": 1, "price": 12, "fee": 1},
            {"event_id": "2", "symbol": "BTC", "side": "SELL", "qty": 1, "price": 12, "fee": 1},
        ]
    )
    assert tape["positions"]["BTC"] == 1
    assert tape["cash_delta"] == -10
    assert tape["records"] == 2


def test_hot_path_is_deterministic_and_ordered() -> None:
    manifest = _manifest()
    calls = []

    def signal(obs, man):  # type: ignore[no-untyped-def]
        calls.append("signal")
        return {"strength": obs["x"]}

    def allocator(sig, man):  # type: ignore[no-untyped-def]
        calls.append("allocator")
        return {"qty": sig["strength"]}

    def risk(order, man):  # type: ignore[no-untyped-def]
        calls.append("risk")
        return order

    def adapter(order, man):  # type: ignore[no-untyped-def]
        calls.append("adapter")
        return {**order, "post_only": True}

    first = deterministic_hot_path(manifest, {"x": 2}, signal, allocator, risk, adapter)
    second = deterministic_hot_path(manifest, {"x": 2}, signal, allocator, risk, adapter)
    assert calls[:4] == ["signal", "allocator", "risk", "adapter"]
    assert first["path_hash"] == second["path_hash"]
    with pytest.raises(ValueError):
        deterministic_hot_path({}, {"x": 1}, signal, allocator, risk, adapter)


def test_latency_and_recovery_permission_boundaries() -> None:
    metrics = latency_metrics(
        {"signal": 0, "observation": 1, "decision": 2, "order": 3, "fill": 100},
        half_life_seconds=100,
        edge_bps=20,
    )
    assert metrics["cadence_regret_bps"] == pytest.approx(10)
    assert latency_metrics({"signal": 1}, half_life_seconds=1, edge_bps=1)["status"] == "UNMEASURED"
    assert (
        autonomous_recovery_plan(
            component="risk",
            failure_class="down",
            capital_critical=True,
            legal_fallback="restart",
            attempts=0,
        )["action"]
        == "SAFE_STOP_AND_ESCALATE"
    )
    assert (
        autonomous_recovery_plan(
            component="report",
            failure_class="stale",
            capital_critical=False,
            legal_fallback="cached",
            attempts=0,
        )["action"]
        == "APPLY_FALLBACK_VERIFY_RECORD"
    )
    assert (
        autonomous_recovery_plan(
            component="report",
            failure_class="stale",
            capital_critical=False,
            legal_fallback="cached",
            attempts=3,
        )["action"]
        == "ESCALATE"
    )
