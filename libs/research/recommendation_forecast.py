"""L1.29 FORECAST INSTRUMENTATION at the recommendation ledger (R0112, decision point D).

WHAT WAS MISSING. `calibrated_confidence` has been shrinking live Kelly sizing since it was built
(run_conviction_trader.py), but the desk logged forecasts at only four places -- traders, a probe,
and engineering tasks. Nothing predicted anything about its OWN pipeline. §42's entire premise is
that every recommendation reaches a disposition, and the desk had never once asked "how many of
these do we actually implement?" -- so its optimism about its own throughput was unfalsifiable.

THE DESIGN CONSTRAINT THAT SHAPED EVERYTHING HERE: an ungraded prediction is worse than no
prediction. It inflates the apparent hit-rate by never counting its misses, and `check_calibration`
already sits at OVERDUE with a pile of rows nobody resolved. So this hook may only exist BECAUSE
it is self-closing: the ledger always knows every row's status, so `settle()` can grade every
past-due forecast deterministically from data that is always present. There is no path where a
`rec:*` forecast rots -- which is the only honest reason to add a fifth writer to a log that is
already failing its fence.

THE PROBABILITY IS MEASURED, NOT INVENTED. p = the desk's own historical implementation rate among
DISPOSED rows. That makes the forecast falsifiable on the desk's own record and self-correcting as
the record grows; a number picked by feel would be calibrating against my taste, not the pipeline.
It is deliberately NOT derived from `roi_bps`: those values are de-facto rank ordinals wearing a
bps label (deep-sweep rows carry 9999/9000/8000/...), so conditioning on them would score noise.

WHY A CONSTANT-PER-ROW FORECAST IS STILL WORTH LOGGING: it cannot rank rows, but it can be WRONG
in a direction. If the desk implements 20% of what it ledgers while predicting 60%, that is a
measured, systematic over-confidence about its own conversion -- exactly the bias L1.29 exists to
feed back, and exactly the bias no amount of introspection reveals.

Pure stdlib + libs.self_improvement.forecast_calibration. import from
libs.research.recommendation_forecast.
"""
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# forecast_calibration is PURE STDLIB, but `libs/self_improvement/__init__.py` eagerly re-exports
# the whole Stage-13 surface, which pulls pydantic -- so importing the package at all requires the
# venv. The ledger CLI is conventionally invoked as `python3 scripts/recommendations.py`, where
# pydantic is absent, and the hook would then be permanently and silently dead: an instrumentation
# organ reporting nothing looks exactly like one with nothing to report. The normal import is the
# fast path; the file load is the fallback and reaches the SAME module file writing the SAME JSON,
# and the module holds no state between calls, so the two paths cannot diverge.
try:
    from libs.self_improvement import forecast_calibration as fc
except ImportError:                                        # pragma: no cover -- stdlib-only host
    _src = Path(__file__).resolve().parents[1] / "self_improvement/forecast_calibration.py"
    _spec = importlib.util.spec_from_file_location("_forecast_calibration_direct", _src)
    if _spec is None or _spec.loader is None:              # the file itself is missing: real error
        raise
    fc = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(fc)

#: Prior used only until the desk has enough disposed rows to measure its own rate. Deliberately
#: pessimistic relative to intent: over-predicting implementation is the desk's expected bias
#: (everything looks implementable when it is ledgered), and a prior that starts where the bias
#: points would hide the very thing this measures for as long as it is in force.
_COLD_START_P = 0.35
#: Below this many disposed rows the measured rate is noise; the prior stands and says so.
_MIN_DISPOSED = 10
#: How long a row gets before the forecast is graded, when it carries no explicit `due`.
_DEFAULT_HORIZON_D = 14


def key_for(rid: str) -> str:
    return f"rec:{rid}"


def _parse(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def base_rate(rows: list[dict[str, Any]], *, horizon_d: int = _DEFAULT_HORIZON_D,
              now: datetime | None = None) -> tuple[float, int, str]:
    """(p, n_eligible, provenance) -- the rate of reaching IMPLEMENTED WITHIN `horizon_d` days.

    THE ESTIMATOR MUST MATCH THE CLAIM, and the obvious version does not. Conditioning on rows
    that reached a terminal status gives 0.9514 on this ledger (137 implemented / 144 terminal)
    -- survivorship, because a row that is never decided never enters the denominator, and 117
    open plus 81 scheduled rows are exactly the ones that failed to be implemented. Forecasting
    0.95 off that would instrument a systematic over-confidence INTO the calibration system built
    to detect it, which is worse than not forecasting at all.

    So the denominator is every row RAISED at least `horizon_d` days ago -- each has had its full
    window and its outcome is known -- and the numerator is those implemented WITHIN that window.
    Still-open and still-scheduled rows count as misses, which is what they are: the claim is
    'implemented BY a date', never 'implemented eventually'.
    """
    now = now or datetime.now(tz=UTC)
    cutoff = now - timedelta(days=horizon_d)
    eligible, hits = 0, 0
    for r in rows:
        raised = _parse(r.get("raised"))
        if raised is None or raised > cutoff:
            continue                       # window not yet elapsed: the outcome is not known yet
        eligible += 1
        if str(r.get("status", "")).lower() != "implemented":
            continue
        disposed = _parse(r.get("disposed"))
        # No disposal stamp on an implemented row: credit it. The stamp is bookkeeping, and
        # withholding credit for a missing field would understate the desk's real throughput.
        if disposed is None or (disposed - raised) <= timedelta(days=horizon_d):
            hits += 1
    if eligible < _MIN_DISPOSED:
        return _COLD_START_P, eligible, f"COLD-START prior ({eligible} < {_MIN_DISPOSED} elapsed)"
    return round(hits / eligible, 4), eligible, f"MEASURED on rows raised >{horizon_d}d ago"


def on_add(rid: str, rows: list[dict[str, Any]], *, due: str | None = None,
           now: datetime | None = None) -> dict[str, Any] | None:
    """Pre-register 'this row reaches IMPLEMENTED by its deadline'. Logged exactly once.

    Returns the forecast payload, or None if this row already carries one -- re-logging would roll
    `resolve_by` forward on every call and blind the overdue check, which is the documented misuse
    of log_forecast and the reason it is guarded by a get_forecast read.
    """
    k = key_for(rid)
    if fc.get_forecast(k) is not None:
        return None
    now = now or datetime.now(tz=UTC)
    p, n, prov = base_rate(rows)
    resolve_by = due or (now + timedelta(days=_DEFAULT_HORIZON_D)).isoformat()
    # The claim carries the row id because _scoreable collapses duplicate claim strings to a
    # single observation -- a shared claim would make every future row score as one.
    claim = f"{rid} reaches IMPLEMENTED by {str(resolve_by)[:10]}"
    fc.log_forecast(k, p, kind="recommendation", resolve_by=str(resolve_by), claim=claim)
    return {"key": k, "p": p, "n_disposed": n, "provenance": prov, "resolve_by": str(resolve_by)}


def settle(rows: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Grade every past-due `rec:*` forecast from the ledger. THE SELF-CLOSING HALF.

    A row's status is always readable, so there is no state in which a forecast here cannot be
    graded -- which is why this hook was allowed to exist at all. IMPLEMENTED is the predicted
    event; everything else at the deadline (rejected, scheduled, still open) is the event not
    happening, because the prediction was about reaching implementation BY a date, not eventually.
    """
    now = now or datetime.now(tz=UTC)
    by_id = {str(r.get("id")): r for r in rows}
    settled: list[dict[str, Any]] = []
    for k, f in (fc._load().get("forecasts") or {}).items():
        if not k.startswith("rec:") or f.get("resolved"):
            continue
        raw = f.get("resolve_by")
        if not isinstance(raw, str):
            continue
        try:
            when = datetime.fromisoformat(raw)
        except ValueError:
            continue                       # unparseable deadline: left alone, never force-graded
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if when > now:
            continue
        row = by_id.get(k.split(":", 1)[1])
        if row is None:
            continue                       # a vanished row is not evidence about a forecast
        outcome = str(row.get("status", "")).lower() == "implemented"
        fc.resolve(k, outcome)
        settled.append({"key": k, "outcome": outcome, "status": row.get("status")})
    return settled
