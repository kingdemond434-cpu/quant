"""One-time forward-window restart for corrected session-filter execution.

The gauntlet used the session filter, but shadow/Fusion/E8 stripped the selector before
execution. Earlier shadow observations therefore measured a different rule. Archive them,
start a new clock through the existing clock ledger and canonical sleeve registry, and let
the ordinary replay count only trades after that new start. No orders are placed here.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mt5desk.family_call import certified_session_filter, session_filter, session_window
from mt5desk.family_inputs import runtime_call_params, strip_identity_keys

import sleeve_registry

# Code-behaviour hashes (not source/comment hashes) make any future session-contract edit open
# another honest window automatically. The forward evidence cannot silently outlive its filter.
# VERSION is kept as the clock's NAME (it is what `sleeve_registry.verify` compares); whether a
# window must restart is decided by CONTRACT below, never by VERSION alone.
VERSION = "session-" + hashlib.sha256("|".join(
    sleeve_registry.behaviour_hash(fn) for fn in
    (session_filter, certified_session_filter, runtime_call_params, strip_identity_keys)
).encode("ascii")).hexdigest()[:16]

#: Statuses a migration never revives. Their clocks keep replaying under the corrected filter.
TERMINAL = ("KILL", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "QUARANTINED", "IDENTITY_BROKEN")


def contract_fingerprint() -> str:
    """What the four helpers DO, measured on a fixed probe, not how their bytecode reads.

    A bytecode hash moves on a refactor, a constant fold or a Python upgrade that changes no
    output, and every such move restarted every session clock (audit 2026-10-06). This hashes
    the helpers' OUTPUTS: which of 25 hourly signals each session keeps, flat and nested
    envelopes, and the call params each emits for a probe that carries every identity key. A
    logic change that alters any output still opens a new window; a change that alters none does
    not.
    """
    sigs = [SimpleNamespace(time=datetime(2026, 1, 5, h, tzinfo=UTC)) for h in range(24)]
    sigs.append(SimpleNamespace(time=None))
    sessions = ("asia", "london", "ny", "all", "ASIA ", None, "unknown")
    kept = {str(s): [sigs.index(g) for g in session_filter(sigs, s)] for s in sessions}
    envelopes = [{"params": {"session": "asia"}}, {"params": {"params": {"session": "ny"}}},
                 {"params": None}, {}]
    cert = [[sigs.index(g) for g in certified_session_filter(sigs, e)] for e in envelopes]
    probe = {"session": "london", "peer_symbol": "EURUSD", "factor_symbols": ["XAUUSD"],
             "input_symbol": "USDJPY", "input_source": "fred", "timeframe": "H1",
             "lookback": 20, "threshold": 1.5}
    calls = {fam: {"runtime": runtime_call_params(fam, dict(probe)),
                   "stripped": strip_identity_keys(fam, dict(probe)),
                   "kept_session": strip_identity_keys(fam, dict(probe), preserve_session=True)}
             for fam in ("session_range_breakout", "cross_asset_residual", "carry")}
    blob = json.dumps({"kept": kept, "cert": cert, "calls": calls}, sort_keys=True, default=str)
    return "contract-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


CONTRACT = contract_fingerprint()
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
    if state.get("runtime_version") == VERSION or state.get("runtime_contract") == CONTRACT:
        # Same name, or same behaviour under a new name (bytecode drift): nothing to restart.
        state["runtime_contract"] = CONTRACT
        return False
    if str(state.get("runtime_version") or "").startswith("session-") and \
            not state.get("runtime_contract"):
        # LEGACY ADOPTION, ONCE: this window was already opened under corrected execution and
        # predates the content fingerprint, so the only thing known to differ is bytecode. It is
        # adopted under the current contract, never reset; from here on content decides.
        state["runtime_contract"] = CONTRACT
        state["runtime_contract_adopted_from"] = state.get("runtime_version")
        return False
    if str(state.get("status") or "ACTIVE").upper() in TERMINAL:
        # A TERMINAL CLOCK IS NEVER REVIVED AND NEVER FROZEN. Raising here used to abort the
        # sleeve every pass (shadow_forward isolates and swallows it), so a PROMOTED sleeve's
        # forward evidence stopped and automatic retirement went blind (audit 2026-10-06). The
        # replay below recomputes every trade under the corrected filter, so evidence keeps
        # flowing; the verdict it carries was taken under the old rule, and that is stated.
        state["runtime_window"] = {
            "status": "UNMEASURED",
            "why": (f"{key}: the {state.get('status')} verdict was taken under runtime "
                    f"{state.get('runtime_version') or 'legacy-unfiltered'}; evidence now replays "
                    f"under {CONTRACT} and the verdict is not re-taken here"),
            "contract": CONTRACT}
        return False
    sleeve_registry.assert_runtime_window_restartable(key)
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
    state["runtime_contract"] = CONTRACT
    state["forward_start"] = start
    state["status"] = "ACTIVE"
    state.update({"n": 0, "cum_r": 0.0, "exp_r": 0.0, "max_dd_r": 0.0,
                  "first_entry": None, "last_entry": None, "days_active": 0,
                  "promotion_authority": False, "order_authority": False,
                  "evidence_note": "session execution corrected; new forward window started"})
    return True
