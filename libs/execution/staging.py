"""Live-deployment stage machine (S0 -> S1 -> S2). Pure state logic, no exchange calls.

Per docs/LIVE_CONNECTOR_SPEC.md section 2:
  S0 testnet/paper (current) -> S1 live-minimum -> S2 full automation.
  S1 entry (Gate 0): principal places keys + explicit sign-off; capital fraction <= 0.10 of
    authorized live capital; 4-5 liquid symbols at venue-minimum notional.
  S2 entry (automatic, ALL must hold): >=8 weeks live, >=10 resolved calibration rows, 0
    critical drill failures, realized cost <= 1.25x modeled.
  Any tripwire demotes ONE stage instantly; demotions are unlimited and never gated. Promotion
  never skips a stage. Every transition is logged to state["history"] for auditability.

State lives in data/stage_state.json. This module only reads/writes that file and evaluates the
evidence dict the CALLER supplies -- it does not itself measure live_weeks, calibration rows,
etc. (those live in their own state files); keeping the gate arithmetic here and the measurement
elsewhere keeps this file pure and easy to property-test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.core.logging import get_logger

# OBSERVABILITY (gap #56, 2026-07-29): the state file records WHERE the machine is; the log
# records WHY it moved, at the moment it moved. state["history"] survives, but a demotion that
# is instantly followed by a crash left no trail of the reason before this. Library never
# configures handlers -- the owning script does.
_log = get_logger(__name__)

_STATE = Path("data/stage_state.json")
_STAGES = ("S0", "S1", "S2")


def _load() -> dict[str, Any]:
    try:
        d = json.loads(_STATE.read_text("utf-8"))
        if isinstance(d, dict) and d.get("stage") in _STAGES:
            d.setdefault("history", [])
            return d
    except (OSError, json.JSONDecodeError):
        pass
    return {"stage": "S0", "history": []}


def _save(state: dict[str, Any]) -> None:
    _STATE.write_text(json.dumps(state, indent=2), "utf-8")


def current_stage() -> str:
    return str(_load().get("stage", "S0"))


def s1_entry_met(evidence: dict[str, Any]) -> tuple[bool, str]:
    """Mechanical S1 (Gate 0) preconditions. ``principal_signoff`` is a human act the caller
    records after the fact -- this function never fabricates consent, it only checks the flag."""
    checks = {
        "principal_signoff": bool(evidence.get("principal_signoff")),
        "capital_fraction_le_010": float(evidence.get("capital_fraction", 1.0)) <= 0.10,
        "symbol_count_4_5": 4 <= int(evidence.get("symbol_count", 0)) <= 5,
        "keys_present": bool(evidence.get("keys_present")),
        "connector_verified": bool(evidence.get("connector_verified")),
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def s2_entry_met(evidence: dict[str, Any]) -> tuple[bool, str]:
    """S2 entry: automatic, numeric, no discretionary language -- ALL must hold."""
    checks = {
        "live_weeks_ge_8": float(evidence.get("live_weeks", 0.0)) >= 8.0,
        "calibration_rows_ge_10": int(evidence.get("calibration_rows", 0)) >= 10,
        # FAIL-CLOSED DEFAULT (2026-07-29, found by mutation testing -- gap #53). This read
        # `evidence.get("critical_drill_failures", 0) == 0`, so an ABSENT drill record was treated
        # as "zero failures" and the S2 gate PASSED on missing evidence. Every other check here
        # already defaults to the refusing side (live_weeks 0.0, calibration_rows 0, cost_ratio
        # 999.0); this one alone defaulted permissive. A sentinel of -1 keeps "0 failures" as the
        # only passing value while making "no record" a refusal. Direction is strictly
        # conservative: this can only ever DECLINE a promotion, never authorise a trade.
        "critical_drill_failures_eq_0": int(evidence.get("critical_drill_failures", -1)) == 0,
        "realized_cost_le_1_25x": float(evidence.get("cost_ratio", 999.0)) <= 1.25,
    }
    return all(checks.values()), ", ".join(f"{k}={v}" for k, v in checks.items())


def promote(evidence: dict[str, Any]) -> tuple[bool, str]:
    """Attempt to advance exactly one stage. Never skips S1 to reach S2 from S0."""
    state = _load()
    stage = state["stage"]
    if stage == "S0":
        met, why = s1_entry_met(evidence)
        target = "S1"
    elif stage == "S1":
        met, why = s2_entry_met(evidence)
        target = "S2"
    else:
        return False, "already at S2 (terminal stage)"
    if not met:
        _log.info("promote REFUSED from %s: %s", stage, why)
        return False, f"gate not met: {why}"
    state["stage"] = target
    state["history"].append({
        "ts": datetime.now(tz=UTC).isoformat(), "action": "promote",
        "from": stage, "to": target, "evidence": why,
    })
    _save(state)
    _log.warning("STAGE PROMOTED %s -> %s: %s", stage, target, why)
    return True, f"promoted {stage} -> {target}: {why}"


def demote(reason: str) -> tuple[bool, str]:
    """Demote exactly one stage. Unlimited, instant, never gated by evidence."""
    state = _load()
    stage = state["stage"]
    idx = _STAGES.index(stage)
    if idx == 0:
        return False, "already at S0 (floor stage)"
    target = _STAGES[idx - 1]
    state["stage"] = target
    state["history"].append({
        "ts": datetime.now(tz=UTC).isoformat(), "action": "demote",
        "from": stage, "to": target, "reason": reason,
    })
    _save(state)
    # A demotion is the risk machinery working; it is logged at WARNING because it must be
    # visible in any live-session log without raising the level.
    _log.warning("STAGE DEMOTED %s -> %s: %s", stage, target, reason)
    return True, target
