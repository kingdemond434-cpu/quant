"""One-time forward-window restart for corrected session-filter execution.

The gauntlet used the session filter, but shadow/Fusion/E8 stripped the selector before
execution. Earlier shadow observations therefore measured a different rule. Archive them,
start a new clock through the existing clock ledger and canonical sleeve registry, and let
the ordinary replay count only trades after that new start. No orders are placed here.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mt5desk.family_call import certified_session_filter, session_filter, session_window
from mt5desk.family_inputs import runtime_call_params, strip_identity_keys

import sleeve_registry

# Code-behaviour hashes (not source/comment hashes) make any future session-contract edit open
# another honest window automatically. The forward evidence cannot silently outlive its filter.
VERSION = "session-" + hashlib.sha256("|".join(
    sleeve_registry.behaviour_hash(fn) for fn in
    (session_filter, certified_session_filter, runtime_call_params, strip_identity_keys)
).encode("ascii")).hexdigest()[:16]
SUMMARY_KEYS = ("n", "cum_r", "exp_r", "max_dd_r", "first_entry", "last_entry",
                "forward_start", "days_active", "status")


def ensure(key: str, params: dict[str, Any], state: dict[str, Any], *, ledger: Path,
           now: datetime | None = None, clock_path: Path | None = None) -> bool:
    """Restart one affected clock at most once. Return True only on state migration.

    If any durable writer fails, raise: the shadow pass must not count old evidence under
    the corrected signal function. Registry and ledger writes are idempotent across retries.
    """
    if session_window(params.get("session")) is None:
        return False
    if state.get("runtime_version") == VERSION:
        return False
    import clock_ledger

    proposed = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    prior = {k: state.get(k) for k in SUMMARY_KEYS if k in state}
    # A named new identity closes the old clock in the immutable ledger; its old start and
    # evidence remain auditable. A retry of this identity returns the first new start.
    kwargs = {"path": clock_path} if clock_path is not None else {}
    clock = clock_ledger.stamp(key, VERSION, proposed, force_new=True, **kwargs)
    start = sleeve_registry.restart_runtime_window(key, VERSION, clock["start"], prior)
    # Keep the old replay snapshot OUTSIDE ledger_*.json: research consumers glob that pattern
    # as active evidence. Legacy filenames may themselves be shared by parameter variants,
    # so the state/registry summaries above are the per-clock audit, not a claim that this file
    # uniquely represented this particular parameterization.
    archive = ledger.parent / "archived_runtime_windows" / (
        f"{ledger.stem}.{hashlib.sha256(key.encode()).hexdigest()[:12]}.pre_{VERSION}.json")
    if ledger.exists() and not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ledger, archive)
    state.setdefault("runtime_windows_before", []).append({
        "version": state.get("runtime_version") or "legacy-unfiltered",
        "summary": prior, "legacy_ledger_may_be_shared": True,
        "archived_ledger": str(archive) if archive.exists() else None,
        "ended_at": start})
    state["identity"] = VERSION
    state["runtime_version"] = VERSION
    state["forward_start"] = start
    state.update({"n": 0, "cum_r": 0.0, "exp_r": 0.0, "max_dd_r": 0.0,
                  "first_entry": None, "last_entry": None, "days_active": 0,
                  "promotion_authority": False, "order_authority": False,
                  "evidence_note": "session execution corrected; new forward window started"})
    return True
