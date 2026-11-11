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

from mt5desk.family_call import (
    SESSIONS,
    certified_session,
    certified_session_filter,
    session_filter,
    session_window,
)
from mt5desk.family_inputs import IDENTITY_KEYS, runtime_call_params, strip_identity_keys

import sleeve_registry

# Code-behaviour hashes (not source/comment hashes) make any future session-contract edit open
# another honest window automatically. The forward evidence cannot silently outlive its filter.
# `behaviour_hash` is deterministic across processes (it recurses into nested code objects and
# sorts sets); before 2026-10-06 it took `repr` of a comprehension's code object, which carries a
# memory address, so VERSION differed in every process and every session clock restarted on
# every pass.
VERSION = "session-" + hashlib.sha256("|".join(
    sleeve_registry.behaviour_hash(fn) for fn in
    (session_filter, certified_session_filter, runtime_call_params, strip_identity_keys,
     session_window, certified_session)
).encode("ascii")).hexdigest()[:16]

#: The identity keys as of 2026-10-06, probed ALONGSIDE the live set: dropping one changes what
#: the strip emits and so opens a new window; adding one is probed through the live set.
_PROBED_IDENTITY_KEYS = ("factor_symbols", "input_source", "input_symbol", "peer_symbol",
                         "session", "surface_generated_at", "timeframe")


def _probe_sessions() -> list[Any]:
    names: set[str] = {"asia", "london", "ny", "all", "overlap", "unknown", "ASIA ", " Ny"}
    names.update(str(k) for k in SESSIONS)
    try:
        import axis_registry
        names.update(str(k) for k in axis_registry.SESSIONS)
        names.update(str(k) for k in axis_registry.SESSION_ALIAS)
        names.update(str(v) for v in axis_registry.SESSION_ALIAS.values())
    except ImportError:
        pass
    return [None, *sorted(names)]


def _probe_families() -> list[str]:
    fams = {"session_range_breakout", "cross_asset_residual", "carry"}
    try:
        from mt5desk.families import FAMILY_REGISTRY
        fams.update(str(k) for k in FAMILY_REGISTRY)
    except ImportError:
        pass
    return sorted(fams)


def contract_fingerprint() -> str:
    """What the four helpers DO, measured on a wide probe: a SECOND restart trigger beside
    VERSION, never a substitute for it (audit 2026-10-06: content alone missed changes the probe
    did not reach).

    The probe: every session spelling in family_call.SESSIONS and the axis registry's SESSIONS
    and SESSION_ALIAS; naive and aware signals at :00 and :30 of every hour plus one with no time;
    flat, nested and empty envelopes; and the call params every registered family gets from a
    probe carrying every identity key (the live set and the 2026-10-06 set). The hash is over
    OUTPUTS, reduced so that a spelling or family that behaves exactly like the default adds
    nothing: registering a new family or alias that the helpers treat identically does not
    restart a window, while any helper change that alters an output does.
    """
    sigs: list[Any] = []
    for h in range(24):
        for m in (0, 30):
            sigs.append(SimpleNamespace(time=datetime(2026, 1, 5, h, m)))  # noqa: DTZ001 (naive on purpose)
            sigs.append(SimpleNamespace(time=datetime(2026, 1, 5, h, m, tzinfo=UTC)))
    sigs.append(SimpleNamespace(time=None))
    default = [sigs.index(g) for g in session_filter(sigs, "unknown-session-probe")]
    kept: dict[str, list[int]] = {}
    for sess in _probe_sessions():
        out = [sigs.index(g) for g in session_filter(sigs, sess)]
        if out != default:
            kept[str(sess)] = out
    envelopes = [{"params": {"session": "asia"}}, {"params": {"params": {"session": "ny"}}},
                 {"params": {"session": "london"}}, {"params": None}, {}]
    cert = [[sigs.index(g) for g in certified_session_filter(sigs, e)] for e in envelopes]
    keys = sorted(set(_PROBED_IDENTITY_KEYS) | {str(k) for k in IDENTITY_KEYS})
    probe = {k: f"probe:{k}" for k in keys}
    probe.update({"session": "london", "lookback": 20, "threshold": 1.5})
    shapes = {json.dumps([runtime_call_params(fam, dict(probe)),
                          strip_identity_keys(fam, dict(probe)),
                          strip_identity_keys(fam, dict(probe), preserve_session=True)],
                         sort_keys=True, default=str)
              for fam in _probe_families()}
    blob = json.dumps({"default": default, "kept": kept, "cert": cert,
                       "calls": sorted(shapes)}, sort_keys=True, default=str)
    return "contract-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


CONTRACT = contract_fingerprint()


def _is_terminal(status: object) -> bool:
    """The forward clock's own terminal rule (`shadow_forward._is_terminal`), so every spelling it
    treats as terminal -- KILL_*, PROMOTED, ... -- is never reset here, EXCEPT a PROMOTION
    CANDIDATE: the promoter writes a LIVE row on that status alone, so a candidate judged under
    the old session rule must re-earn it under the corrected one (reset to ACTIVE, n=0, no
    authority), never carry it to LIVE on stale evidence (audit 2026-10-06)."""
    if str(status or "").strip().upper().replace("_", " ").startswith("PROMOTION CANDIDATE"):
        return False
    try:
        from research.shadow_forward import _is_terminal as rule
    except ImportError:
        from shadow_forward import _is_terminal as rule
    return bool(rule(status))


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
    if (state.get("runtime_version") == VERSION
            and state.get("runtime_contract") in (CONTRACT, None)):
        # The same bytecode, and the same behaviour (or a window opened under this VERSION before
        # the fingerprint existed, stamped once): nothing changed, nothing to restart. Anything
        # else -- a new VERSION, or the same VERSION with different outputs -- restarts below.
        state["runtime_contract"] = CONTRACT
        return False
    if _is_terminal(state.get("status") or "ACTIVE"):
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
