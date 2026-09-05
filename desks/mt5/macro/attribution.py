"""POST-EVENT ATTRIBUTION -- the loop that makes the intelligence grow.

THIS IS THE ANSWER TO "NOT JUST HARDCODED DATA", and it is worth more than any additional source.
A source added without this produces more rows nobody learns from. This module marks the desk's
homework: after every event, at horizon, it measures what actually happened and feeds the answer
back into each of the four learned things in this package.

WHAT IS MEASURED, AND WHAT EACH MEASUREMENT UPDATES.

    who arrived first        source latency ranking       -> credibility speed (`lead_s`)
    did the claim hold       verified / falsified          -> credibility posterior (both levels)
    which instrument led     largest |move| earliest       -> which candidates to price against
    what the factors did     measured factor response      -> category -> factor loadings
    how much was left        realised unpriced fraction    -> calibration of `priced.estimate`
    was the forecast right   sign and magnitude error      -> overreaction diagnosis
    what would have been best argmax over weight deltas    -> the E[log W] benchmark

VERIFICATION IS A PRICE QUESTION HERE, AND THE LIMIT IS STATED. This module can measure whether a
claim was FOLLOWED BY the move it implied; it cannot in general check whether the claim was
factually true. Those differ, and conflating them would score a true report that the market
ignored as a falsehood. So the counters are named for what they are -- `move_confirmed` and
`move_contradicted` -- and `credibility.py` consumes them as the best available proxy while the
report says exactly that. A factual-verification feed would be strictly better and is named as a
gap rather than faked.

E[log W] IS THE BENCHMARK BECAUSE IT IS THE DESK'S OBJECTIVE. "Which forecast was right" is a
weaker question than "what response would have maximised expected log wealth", and only the
second is comparable across events of different sizes. The grid search here is deliberately
coarse and single-instrument: it is a BENCHMARK for the event layer's forecasts, not a portfolio
solve. The portfolio solve is the allocator's, always.

MULTIPLICITY IS CHARGED HERE TOO. Every category-conditional statistic this module produces goes
back through `factors.category_loadings`, which charges its cells and widens its intervals. An
attribution pass makes admission harder, never easier -- which is the right incentive for a loop
that runs after every single event.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from .factors import FactorBasis, measure_response
from .ledger import MACRO_DIR, EventLedger, write_json_atomic
from .priced import realised_unpriced
from .prices import PriceReader, move_sigma
from .schema import EventRecord, Status, now_iso, parse_ts

ATTRIBUTION_PATH = MACRO_DIR / "event_attribution.jsonl"
ATTRIBUTION_REPORT = MACRO_DIR / "ATTRIBUTION.json"

#: Default horizon over which an event's full response is judged. One trading day: long enough
#: that the post-release drift and the reversal have both had their say (`libs/regime/
#: event_state.py` distinguishes those phases), short enough that the next day's news is not
#: being attributed to this event.
DEFAULT_HORIZON_S = 86400.0

#: The candidate responses the E[log W] benchmark searches over, as signed fractions of a unit
#: of heat. Coarse on purpose: the benchmark answers "should the desk have leaned into this, and
#: roughly how hard", not "what is the optimal weight" -- that is the allocator's question.
RESPONSE_GRID: tuple[float, ...] = (-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0)

__all__ = [
    "DEFAULT_HORIZON_S",
    "RESPONSE_GRID",
    "Attribution",
    "attribute",
    "feedback",
    "report",
]


@dataclass(frozen=True)
class Attribution:
    event_id: str
    category: str
    source_id: str
    status: str
    #: Seconds from publication to this desk having the bytes. The cost of the source.
    arrival_lag_s: float | None = None
    #: Seconds from arrival to the first material move. NEGATIVE means the move came first --
    #: the desk was late, and the information was never tradeable through this source.
    lead_s: float | None = None
    leading_instrument: str | None = None
    leading_move_sigma: float | None = None
    factor_response: dict[str, float] = field(default_factory=dict)
    realised_unpriced: float | None = None
    estimated_unpriced: float | None = None
    unpriced_error: float | None = None
    #: Seconds after arrival by which HALF the post-arrival move had happened. This is the decay
    #: rate of the information that was still tradeable, and it is the number `interrupt.py`
    #: needs: an event whose half-life is longer than the allocator's fast clock has no case for
    #: preempting it. Nothing else in the package measures it, so without this the interrupt gate
    #: would be permanently UNMEASURED and the interrupt would be dead code by construction.
    unpriced_half_life_s: float | None = None
    forecast_error: dict[str, float] = field(default_factory=dict)
    overreaction: float | None = None
    move_confirmed: bool | None = None
    best_response: float | None = None
    best_log_growth: float | None = None
    realised_log_growth: float | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["at"] = now_iso()
        return d


def _first_material_move(reader: PriceReader, symbols: Sequence[str], t0: Any,
                         horizon_s: float, threshold_sigma: float = 1.0
                         ) -> tuple[str | None, float | None, float | None]:
    """The instrument that moved first past `threshold_sigma`, and how long it took.

    Walks the window in bar steps rather than assuming a granularity, so an H1-only box gives an
    hourly answer and says so through the step size rather than pretending to minutes.
    """
    best: tuple[str | None, float | None, float | None] = (None, None, None)
    for sym in symbols:
        span = reader.bar_span_s(sym)
        if span is None or span <= 0:
            continue
        steps = int(max(1, min(400, horizon_s // span)))
        for i in range(1, steps + 1):
            t1 = t0 + timedelta(seconds=span * i)
            val, _ = move_sigma(reader, sym, t0, t1)
            if val is None:
                continue
            if abs(val) >= threshold_sigma:
                elapsed = span * i
                if best[2] is None or elapsed < best[2]:
                    best = (sym, val, elapsed)
                break
    return best


def _unpriced_half_life(reader: PriceReader, symbol: str | None, t0: Any,
                        horizon_s: float) -> float | None:
    """Seconds after arrival by which half the post-arrival move had happened.

    Walks the window in bar steps and returns the first step at which the cumulative move from
    arrival reaches half of the full-window move. Returns None when the full move is negligible
    (nothing decayed because nothing happened) or when the bars are too coarse to resolve it --
    a half-life quoted at the granularity of the only bar available would be an artefact of the
    data, and the interrupt would then be gated on the desk's bar size rather than on the world.
    """
    if symbol is None:
        return None
    span = reader.bar_span_s(symbol)
    if span is None or span <= 0:
        return None
    steps = int(max(1, min(400, horizon_s // span)))
    if steps < 4:
        return None
    total, _ = move_sigma(reader, symbol, t0, t0 + timedelta(seconds=span * steps))
    if total is None or abs(total) < 0.5:
        return None
    for i in range(1, steps + 1):
        part, _ = move_sigma(reader, symbol, t0, t0 + timedelta(seconds=span * i))
        if part is not None and abs(part) >= abs(total) / 2.0:
            return float(span * i)
    return None


def attribute(rec: EventRecord, reader: PriceReader, *, basis: FactorBasis | None = None,
              horizon_s: float = DEFAULT_HORIZON_S,
              candidate_symbols: Sequence[str] | None = None) -> Attribution:
    """Mark one event's homework. Refuses with a reason rather than inventing a verdict."""
    t_rec = parse_ts(rec.received_at)
    t_pub = parse_ts(rec.published_at)
    if t_rec is None:
        return Attribution(rec.event_id, rec.category, rec.source_id, Status.UNMEASURED,
                           note="no receive clock")
    end = t_rec + timedelta(seconds=horizon_s)
    symbols = list(candidate_symbols or rec.instruments or (basis.symbols if basis else ()))
    if not symbols:
        return Attribution(rec.event_id, rec.category, rec.source_id, Status.UNMEASURED,
                           note="no candidate instruments to attribute against")

    lead_sym, lead_move, elapsed = _first_material_move(reader, symbols, t_rec, horizon_s)
    arrival_lag = None if t_pub is None else (t_rec - t_pub).total_seconds()

    factor_response: dict[str, float] = {}
    if basis is not None and basis.status == Status.MEASURED:
        factor_response, _ = measure_response(reader, basis, t0=t_rec, t1=end)

    est = (rec.priced or {}).get("unpriced_fraction")
    realised = (realised_unpriced(reader, symbols=symbols, published_at=rec.published_at or "",
                                  received_at=rec.received_at, horizon_end=end)
                if rec.published_at else None)
    err = (None if est is None or realised is None else round(float(est) - float(realised), 4))

    # Forecast error per instrument, in sigma. The desk's own forecasts are scored against the
    # move that happened AFTER it arrived -- the only part it could have traded.
    ferr: dict[str, float] = {}
    over: float | None = None
    for f in rec.forecasts or []:
        sym = str(f.get("symbol", ""))
        pred = f.get("expected_move_sigma")
        if not sym or not isinstance(pred, int | float):
            continue
        actual, _ = move_sigma(reader, sym, t_rec, end)
        if actual is None:
            continue
        ferr[sym] = round(float(pred) - float(actual), 4)
        if abs(float(actual)) > 1e-9:
            ratio = abs(float(pred)) / abs(float(actual))
            over = ratio if over is None else max(over, ratio)

    best_resp, best_growth, realised_growth = _best_response(
        reader, lead_sym, t_rec, end, rec.forecasts or [])

    confirmed = None
    if lead_move is not None and rec.forecasts:
        preds = [float(f.get("expected_move_sigma", 0.0)) for f in rec.forecasts
                 if str(f.get("symbol", "")) == lead_sym]
        if preds and abs(preds[0]) > 1e-9:
            confirmed = (preds[0] * lead_move) > 0

    return Attribution(
        event_id=rec.event_id, category=rec.category, source_id=rec.source_id,
        status=Status.MEASURED if lead_sym else Status.UNMEASURED,
        arrival_lag_s=arrival_lag,
        lead_s=None if elapsed is None else float(elapsed),
        leading_instrument=lead_sym,
        leading_move_sigma=None if lead_move is None else round(float(lead_move), 4),
        factor_response=factor_response, realised_unpriced=realised,
        estimated_unpriced=None if est is None else float(est), unpriced_error=err,
        unpriced_half_life_s=_unpriced_half_life(reader, lead_sym, t_rec, horizon_s),
        forecast_error=ferr, overreaction=None if over is None else round(over, 3),
        move_confirmed=confirmed, best_response=best_resp, best_log_growth=best_growth,
        realised_log_growth=realised_growth,
        note=("move_confirmed measures whether the implied direction was FOLLOWED BY the move. "
              "It is not factual verification of the claim; a factual-verification feed would "
              "be strictly better and is a named gap."))


def _best_response(reader: PriceReader, symbol: str | None, t0: Any, t1: Any,
                   forecasts: Sequence[Mapping[str, Any]]
                   ) -> tuple[float | None, float | None, float | None]:
    """Which response on the grid would have maximised realised log growth, and what the desk's
    own forecast would have earned. The benchmark, not a portfolio solve."""
    if symbol is None:
        return None, None, None
    move, _ = move_sigma(reader, symbol, t0, t1)
    if move is None:
        return None, None, None
    # log(1 + w*r) with r taken as the sigma move scaled to a modest unit so the grid is
    # meaningful; the scale cancels in the ARGMAX, which is what is being reported.
    r = float(move) * 0.01
    best_w, best_g = None, None
    for w in RESPONSE_GRID:
        x = 1.0 + w * r
        if x <= 0:
            continue
        g = math.log(x)
        if best_g is None or g > best_g:
            best_w, best_g = w, g
    own = None
    preds = [float(f.get("expected_move_sigma", 0.0)) for f in forecasts
             if str(f.get("symbol", "")) == symbol]
    if preds:
        w = max(-1.0, min(1.0, preds[0]))
        x = 1.0 + w * r
        own = math.log(x) if x > 0 else None
    return best_w, (None if best_g is None else round(best_g, 8)), (
        None if own is None else round(own, 8))


def feedback(attributions: Sequence[Attribution]) -> dict[str, Any]:
    """Turn marked homework into the inputs the next pass fits on. THE GROWTH LOOP.

    Returns exactly the shapes the learners consume: `credibility.fit`'s outcome map,
    `factors.category_loadings`' per-category sample map, and the priced estimator's calibration
    residuals. Nothing here fits anything itself -- keeping measurement and fitting apart is what
    lets the replay refit from the ledger alone and get the same answer.
    """
    outcomes: dict[str, dict[str, Any]] = {}
    factor_samples: dict[str, dict[str, list[float]]] = {}
    decay_samples: dict[str, list[float]] = {}
    calibration: list[float] = []
    for a in attributions:
        if a.unpriced_half_life_s is not None:
            decay_samples.setdefault(a.category, []).append(a.unpriced_half_life_s)
        rec = outcomes.setdefault(a.source_id, {"verified": 0, "falsified": 0, "leads": []})
        if a.move_confirmed is True:
            rec["verified"] += 1
        elif a.move_confirmed is False:
            rec["falsified"] += 1
        if a.lead_s is not None:
            rec["leads"].append(a.lead_s)
        for fid, val in (a.factor_response or {}).items():
            factor_samples.setdefault(a.category, {}).setdefault(fid, []).append(float(val))
        if a.unpriced_error is not None:
            calibration.append(float(a.unpriced_error))
    bias = (sum(calibration) / len(calibration)) if calibration else None
    return {
        "source_outcomes": outcomes,
        "factor_samples": factor_samples,
        # The decay rates the interrupt gate is measured against. Fed back through
        # `EventLedger.category_stats(decay_samples=...)` rather than onto the event rows, which
        # are append-only and record what was known at SCORING time -- what is learned afterwards
        # belongs to the attribution record, not retroactively to the observation.
        "decay_samples": decay_samples,
        "priced_calibration": {
            "n": len(calibration),
            "mean_error": None if bias is None else round(bias, 4),
            "reading": (
                "UNMEASURED -- no attributions with both an estimate and a realisation"
                if bias is None else
                ("the estimator is OPTIMISTIC: it says more information remains than did"
                 if bias > 0 else
                 "the estimator is PESSIMISTIC: it says less information remains than did")),
        },
        "note": ("Consumed by credibility.fit and factors.category_loadings. Every "
                 "category-conditional cell they fit is charged to the multiplicity ledger, so "
                 "running this loop makes admission harder, never easier."),
    }


def report(attributions: Sequence[Attribution], ledger: EventLedger | None = None,
           write: bool = False) -> dict[str, Any]:
    """The human-readable pass: who was fast, who was right, what the desk overpaid for."""
    by_source: dict[str, dict[str, Any]] = {}
    for a in attributions:
        d = by_source.setdefault(a.source_id, {"n": 0, "confirmed": 0, "contradicted": 0,
                                               "lags": [], "leads": []})
        d["n"] += 1
        if a.move_confirmed is True:
            d["confirmed"] += 1
        elif a.move_confirmed is False:
            d["contradicted"] += 1
        if a.arrival_lag_s is not None:
            d["lags"].append(a.arrival_lag_s)
        if a.lead_s is not None:
            d["leads"].append(a.lead_s)
    rows = []
    for sid, d in sorted(by_source.items()):
        lags = d.pop("lags")
        leads = d.pop("leads")
        rows.append({
            "source": sid, **d,
            "median_arrival_lag_s": round(sorted(lags)[len(lags) // 2], 2) if lags else None,
            "median_lead_to_move_s": round(sorted(leads)[len(leads) // 2], 2) if leads else None,
        })
    over = [a.overreaction for a in attributions if a.overreaction is not None]
    fb = feedback(attributions)
    payload = {
        "at": now_iso(),
        "n_attributions": len(attributions),
        "sources": rows,
        "median_overreaction_ratio": (round(sorted(over)[len(over) // 2], 3) if over else None),
        "overreaction_reading": (
            "UNMEASURED" if not over else
            ("the layer is FORECASTING LARGER MOVES THAN HAPPEN -- shrink"
             if sorted(over)[len(over) // 2] > 1.0 else
             "the layer is forecasting smaller moves than happen")),
        "priced_calibration": fb["priced_calibration"],
        "categories_seen": sorted({a.category for a in attributions}),
        "ledger": (ledger.summary() if ledger is not None else None),
        "note": ("Verification here is move-confirmation, not fact-checking. Named as a "
                 "limitation rather than presented as truth."),
    }
    if write:
        write_json_atomic(ATTRIBUTION_REPORT, payload)
        ATTRIBUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(ATTRIBUTION_PATH, "a", encoding="utf-8") as fh:
            for a in attributions:
                fh.write(json.dumps(a.to_dict(), separators=(",", ":"), sort_keys=True,
                                    default=str) + "\n")
    return payload
