"""TRIAL COUNT GUARD: ONE TRIAL ID, AND A BAR THAT NEVER MOVES WITH A TRIAL COUNT.

(principal, 2026-10-13)
    "make sure the bars never raise never ever penalty never inflation due to trials anything
     like that"

Two rules live here, and nowhere else:

1. THE BAR'S N IS FIXED. The Tier S bar is the deflated Sharpe at N = 5 with the per-cell null
   variance 1/(T-1) (owner's T8 ruling, 2026-10-13: a per-cell t of about 2.84). Every organ that
   turns a trial count into a deflated Sharpe, a t-threshold, an E[max] hurdle or a haircut passes
   that count through `bar_n`, which returns `BAR_N` whatever it is handed. A count may be
   REPORTED beside a verdict; it may never raise one. `scripts/check_trial_inflation.py` fails the
   law gate on any bar call whose trials argument does not come from here.

2. THE SAME SPEC IS CHARGED ONCE, EVER. `trial_id` hashes the canonical hypothesis -- family,
   symbol, timeframe, sorted params, side, modifiers -- and nothing about the run that tested it:
   no run id, timestamp, sweep number, retry counter, pass, seat or file name. A re-run, a re-test,
   a sweep retry, a re-queued BUDGET_DEFERRED / FAIL_3X / NOT_RUN cell, a duplicate donation and a
   ledger rebuild all produce the same id, so a ledger that counts distinct ids counts distinct
   hypotheses. That count is kept for the ledger's HONESTY (how much has the desk searched?) and
   it NEVER feeds the bar (rule 1).

Pure and stdlib only, so every lane -- miners, ledgers, judges' reporters, the fence -- can import
it without pulling a framework.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from typing import Any

#: THE BAR'S TRIAL COUNT. Fixed by the owner's T8 ruling; never derived, never raised, never
#: lowered. Changing it is the principal's call and a sealed re-sign, not a session's edit.
BAR_N = 5

#: Keys that describe the RUN, never the hypothesis. `canonical_spec` reads only the identity
#: axes and `params` off a row, so a row's top-level run fields (timestamps, seat, status, file)
#: never enter; these are the run fields that have been seen riding INSIDE params, dropped at every
#: depth. Deliberately narrow: `hour`, `day` or `t` can be a real parameter of a hypothesis.
VOLATILE_KEYS: frozenset[str] = frozenset({
    "run_id", "runid", "pass_id", "pass_no", "sweep", "sweep_id", "sweep_no", "sweep_number",
    "attempt", "attempts", "retry", "retries", "retry_count", "requeue", "requeued",
    "requeue_count", "queued_at", "timestamp", "generated_at", "generated_utc", "created_at",
    "created_utc", "written_at", "judged_at", "judged_utc", "minted_at", "nonce", "job_id",
    "batch_id", "shard_id", "trial_id", "cell_id", "graph_id", "uuid",
})

#: Spellings of the identity axes, folded to one name each.
_ALIASES: dict[str, tuple[str, ...]] = {
    "family": ("family", "fam", "mechanism_family"),
    "symbol": ("symbol", "sym", "instrument", "ticker"),
    "timeframe": ("timeframe", "tf", "chart", "bar", "granularity"),
    "side": ("side", "direction", "dir"),
    "modifiers": ("modifiers", "modifier", "conditioners", "filters", "overlays"),
}


def bar_n(_requested: Any = None) -> int:
    """The trial count a bar may use: always `BAR_N`. The argument is the count the caller
    measured; it is accepted so the call site stays honest about what it had, and ignored so no
    count can ever raise (or lower) the bar."""
    return BAR_N


def _norm(value: Any) -> Any:
    """Canonical, run-free form of a spec value: dict keys sorted, volatile keys dropped, floats
    normalised so 20 and 20.0 hash alike, strings stripped (case kept: params can be case-
    sensitive)."""
    if isinstance(value, Mapping):
        return {str(k): _norm(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
                if str(k).lower() not in VOLATILE_KEYS}
    if isinstance(value, (list, tuple)):
        return [_norm(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_norm(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True,
                                                                          default=str))
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return str(f)
        return int(f) if f.is_integer() else round(f, 12)
    return str(value).strip()


def _pick(spec: Mapping[str, Any], axis: str) -> Any:
    for k in _ALIASES[axis]:
        v = spec.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def canonical_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """The hypothesis a row describes, with every trace of the run removed."""
    params = spec.get("params")
    params = dict(params) if isinstance(params, Mapping) else {}
    tf = _pick(spec, "timeframe")
    if tf is None:  # the desk's producers carry the chart inside params (hypothesis_graph)
        for k in _ALIASES["timeframe"]:
            if params.get(k) not in (None, ""):
                tf = params[k]
                break
    params = {k: v for k, v in params.items() if k not in _ALIASES["timeframe"] or tf is None}
    mods = _pick(spec, "modifiers")
    if isinstance(mods, (list, tuple, set, frozenset)):
        mods = sorted(str(_norm(m)) for m in mods)
    sym = _pick(spec, "symbol")
    side = _pick(spec, "side")
    return {
        "family": str(_pick(spec, "family") or "").strip().lower(),
        "symbol": str(sym or "").strip().upper(),
        "timeframe": str(tf or "").strip().upper(),
        "params": _norm(params),
        "side": str(side).strip().lower() if side is not None else "",
        "modifiers": _norm(mods) if mods is not None else [],
    }


def trial_id(spec: Mapping[str, Any]) -> str:
    """sha256 of the canonical spec, 24 hex chars. The same hypothesis gets the same id however
    many times, by whomever, in whichever sweep it was tested."""
    payload = json.dumps(canonical_spec(spec), sort_keys=True, separators=(",", ":"),
                         default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def distinct(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """{trial_id: times seen} over spec rows. len() is the honest distinct count; the values
    say how often each spec was charged by a counter that did not dedupe."""
    seen: dict[str, int] = {}
    for r in rows:
        if isinstance(r, Mapping):
            k = trial_id(r)
            seen[k] = seen.get(k, 0) + 1
    return seen


def run_key(*parts: Any) -> str:
    """A content key for an aggregate counter row (a pass that reports `tests_run` with no cell
    list): the canonical form of what was tested, run fields dropped. Two passes over unchanged
    inputs give the same key, so the ledger charges their count once."""
    payload = json.dumps([_norm(p) for p in parts], sort_keys=True, separators=(",", ":"),
                         default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def canonical_trial_id(spec: Mapping[str, Any]) -> str:
    """THE INTERFACE NAME (Breadth's cell converter imports this). Identical to `trial_id`."""
    return trial_id(spec)


#: Top-level fields of an AGGREGATE counter row (a pass that reports a count, not a cell list)
#: that describe when/which run wrote it. Dropped by `row_key`, so the same pass over the same
#: inputs, written twice, is one row.
ROW_VOLATILE: frozenset[str] = frozenset({
    "ts", "at", "time", "timestamp", "utc", "generated_utc", "generated_at", "created_at",
    "created_utc", "written_at", "run_id", "run", "pass_id", "pass_no", "sweep", "sweep_id",
    "sweep_no", "attempt", "attempts", "retry", "retries", "requeued", "requeue_count", "pid",
    "host", "job_id", "batch_id", "shard_id", "wall_s", "seconds", "elapsed_s",
})


def row_key(row: Mapping[str, Any]) -> str:
    """Content key of an aggregate trial row with its run fields removed. Re-appending the same
    pass's row (a retry, a re-run on unchanged inputs, a ledger rebuild) gives the same key."""
    return run_key({str(k): v for k, v in row.items() if str(k).lower() not in ROW_VOLATILE})


#: THE TIER S t HELPERS, re-exported lazily from `libs.research.tier_s_threshold` so this module
#: stays stdlib-only for the lanes that import it without numpy/scipy.
_TIER_S_EXPORTS = frozenset({"tier_s_t_required", "tier_s_passes", "tier_s_sr0",
                             "tier_s_variance", "TIER_S_DSR_THRESHOLD"})


def __getattr__(name: str) -> Any:
    if name in _TIER_S_EXPORTS:
        from libs.research import tier_s_threshold
        return getattr(tier_s_threshold, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
