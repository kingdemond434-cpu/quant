#!/usr/bin/env python3
"""EXPECTED vs REALIZED -- the only measurement that can say WHICH model was wrong.

    Error = EdgeError + CorrelationError + ExecutionError + RegimeError + TailError
                                                            -- the principal, 2026-09-02

WHY DECOMPOSE AT ALL. A book that underperforms its forecast tells you nothing on its own: the
edges could be decaying, the sleeves could be more correlated than measured, the fills could be
worse than modelled, or the regime could simply be one the book is not built for. Those four
call for four completely different responses -- retire sleeves, re-weight for dependence, fix
execution, or do nothing at all -- and a single "we were 20 bps light" number cannot distinguish
them. This splits the miss into terms that each name a model.

    EDGE          sum_i h_i * (realized_mu_i - expected_mu_i)
                  what the SLEEVES did against what the posterior said they would, at the heat
                  they were actually given. Signed per sleeve, so a decaying edge is named.

    CORRELATION   expected_book_var - realized_book_var, at the solved weights
                  what the book's dispersion did against what the sampled worlds said. Positive
                  means the desk was more diversified than it modelled; negative is the dangerous
                  direction and the one crises produce.

    EXECUTION     realized cost per unit heat - modelled cost per unit heat
                  fills, spread and slippage, isolated from whether the signal was right.

    REGIME        the part of the edge miss explained by the day's regime mix differing from the
                  mix the forecast was drawn under. Charged BEFORE edge error, because punishing
                  a trend sleeve for a range week is how a desk retires its best edges.

    RESIDUAL      whatever the four do not account for. Reported, never distributed -- a residual
                  quietly folded into the other terms is how a decomposition becomes a story.

HONEST WHEN IT CANNOT MEASURE. Every term reports UNMEASURED rather than zero when the evidence
is not there (L1.28a). At the time of writing the live ledger is empty and the forward clocks
carry 1-4 days each, so most of this will read UNMEASURED for a while -- which is the correct
answer and a visible one, rather than a decomposition of noise into four confident numbers.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FORECASTS = BASE / "data" / "pf_forecast_log.jsonl"
LIVE = BASE / "data" / "live_ledger.jsonl"
OUT = BASE / "reports" / "allocator_attribution.json"

#: Minimum scored days before a term is reported as a number rather than UNMEASURED. Below this
#: the decomposition is describing noise, and four confident numbers about noise is worse than
#: one honest refusal.
MIN_DAYS = 5

UNMEASURED = "UNMEASURED"


def load_forecasts(days: int = 30) -> list[dict[str, Any]]:
    """Forecast records within `days`, newest last. Missing file is UNMEASURED, not empty."""
    if not FORECASTS.exists():
        return []
    cutoff = datetime.now(UTC) - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for line in FORECASTS.read_text("utf-8").splitlines():
        try:
            r = json.loads(line)
            when = datetime.fromisoformat(str(r["t"]))
        except (ValueError, KeyError, TypeError):
            continue
        if when >= cutoff:
            r["_when"] = when
            out.append(r)
    return out


def realized_daily() -> tuple[dict[str, dict[str, float]], str]:
    """Per-sleeve realized daily R, live first and forward second, with the basis named.

    THE BASIS IS PART OF THE ANSWER. Live R and shadow-forward R are not the same evidence -- one
    paid real spread on real fills, the other did not -- and an attribution that averages them
    without saying so reports execution error it cannot have measured.
    """
    live: dict[str, dict[str, float]] = defaultdict(dict)
    if LIVE.exists():
        for line in LIVE.read_text("utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            name, day = str(r.get("sleeve") or ""), str(r.get("close_time") or "")[:10]
            try:
                val = float(r.get("r_multiple"))
            except (TypeError, ValueError):
                continue
            if name and day:
                live[name][day] = live[name].get(day, 0.0) + val
    if live:
        return dict(live), "live"
    try:
        from research.portfolio_evidence import daily_series
        fwd = daily_series()
        if fwd:
            return fwd, "shadow_forward"
    except Exception:
        pass
    return {}, UNMEASURED


def _edge_term(forecasts: list[dict[str, Any]], realized: dict[str, dict[str, float]],
               ) -> dict[str, Any]:
    """Heat-weighted miss between what each sleeve did and what it was expected to do.

    Expected per-sleeve mu is not stored per sleeve (the forecast log keeps the book's rate, not
    126 of them), so the reference is the book's own expected rate spread over the heat that was
    actually allocated. That is a coarser question than "was sleeve i's posterior right", and it
    is labelled as such rather than dressed up.
    """
    days: dict[str, float] = {}
    per_sleeve: dict[str, list[float]] = defaultdict(list)
    for f in forecasts:
        day = str(f["t"])[:10]
        book = {str(k): float(v) for k, v in (f.get("book") or {}).items()}
        if not book:
            continue
        got = 0.0
        seen = False
        for name, h in book.items():
            r = realized.get(name, {}).get(day)
            if r is None:
                continue
            seen = True
            got += h * r
            per_sleeve[name].append(h * r)
        if seen:
            days[day] = got - float(f.get("expected_log_per_day") or 0.0)
    if len(days) < MIN_DAYS:
        return {"value": UNMEASURED, "scored_days": len(days),
                "why": f"{len(days)} scored day(s), need {MIN_DAYS}"}
    vals = list(days.values())
    return {
        "value": round(statistics.fmean(vals), 8),
        "scored_days": len(vals),
        "sd": round(statistics.pstdev(vals), 8) if len(vals) > 1 else 0.0,
        "worst_sleeves": dict(sorted(
            ((k, round(statistics.fmean(v), 6)) for k, v in per_sleeve.items() if v),
            key=lambda kv: kv[1])[:8]),
    }


def _dispersion_term(forecasts: list[dict[str, Any]],
                     realized: dict[str, dict[str, float]]) -> dict[str, Any]:
    """Realized book dispersion against the dispersion the sampled worlds implied.

    NEGATIVE IS THE DANGEROUS SIGN: the book moved together more than the model said, which is
    what correlation convergence looks like from the inside and what the crisis worlds exist to
    anticipate. Positive means the desk was luckier than it modelled, which is not a reason to
    size up.
    """
    obs: list[float] = []
    for f in forecasts:
        day = str(f["t"])[:10]
        book = {str(k): float(v) for k, v in (f.get("book") or {}).items()}
        got = [h * realized.get(n, {}).get(day, 0.0) for n, h in book.items()
               if realized.get(n, {}).get(day) is not None]
        if len(got) > 1:
            obs.append(sum(got))
    if len(obs) < MIN_DAYS:
        return {"value": UNMEASURED, "scored_days": len(obs),
                "why": f"{len(obs)} scored day(s), need {MIN_DAYS}"}
    real_sd = statistics.pstdev(obs)
    # The forecast's own tail rate is the model's dispersion claim: CVaR is a quantile of the
    # world population, so |CVaR - mean| scales with how spread out the model thought it was.
    claims = [abs(float(f.get("expected_cvar_per_day") or 0.0)
                  - float(f.get("expected_log_per_day") or 0.0)) for f in forecasts]
    model_sd = statistics.fmean(claims) if claims else 0.0
    return {
        "value": round(model_sd - real_sd, 8),
        "realized_sd": round(real_sd, 8), "model_sd": round(model_sd, 8),
        "scored_days": len(obs),
        "reading": ("the book moved TOGETHER more than modelled" if model_sd < real_sd
                    else "the book was more dispersed than modelled"),
    }


def _regime_term(forecasts: list[dict[str, Any]]) -> dict[str, Any]:
    """How far the regime mix moved across the scored window.

    Charged BEFORE edge error in the reading of this report: a trend sleeve that loses in a range
    week has not decayed, and retiring it would be the desk destroying its own best edges on a
    calendar accident.
    """
    mixes = [f.get("regime") or {} for f in forecasts if f.get("regime")]
    if len(mixes) < 2:
        return {"value": UNMEASURED, "why": "fewer than 2 passes carried a regime mix"}
    keys = sorted({k for m in mixes for k in m})
    first, last = mixes[0], mixes[-1]
    drift = {k: round(float(last.get(k, 0.0)) - float(first.get(k, 0.0)), 4) for k in keys}
    total = sum(abs(v) for v in drift.values()) / 2.0
    return {
        "value": round(total, 4), "drift": drift,
        "reading": ("regime mix materially different from the forecast window"
                    if total > 0.25 else "regime mix broadly unchanged"),
    }


def _execution_term(basis: str) -> dict[str, Any]:
    """Realized fill cost against the modelled cost, from the intent/fill join.

    UNMEASURABLE FROM SHADOW EVIDENCE, AND SAYING SO IS THE POINT. Shadow-forward R multiples are
    computed with the same cost model the forecast used, so differencing them measures the model
    against itself and returns zero -- a zero that would read as "execution is perfect". Only
    live fills can answer this.

    THE ANSWER WAS ALREADY BEING COMPUTED. This used to return UNMEASURED with the reason
    "per-fill slippage capture not yet wired (needs requested vs filled price on the ledger row)".
    That was stale: `mt5desk.markout` has joined `order_intents.jsonl` to `live_ledger.jsonl` by
    order ticket and reported `mean_slip_r` since the first trade -- requested versus filled, per
    fill, in R. The capture was wired; this reader was not. Same shape as every other defect this
    desk finds: the capability was present and unreachable.

    SIGNED SO THE DIRECTION IS UNAMBIGUOUS. Slippage is a subtraction from edge, so the term is
    NEGATIVE when fills are worse than intended. `edge_share` says what fraction of the book's
    measured expectancy execution is eating, which is the number that decides whether an edge is
    worth trading at all.

    REFUSES A MIXED LEDGER. A demo server fills stops at the trigger with no slippage, so
    averaging demo and live rows drags the mean toward "no slippage" using trades that could not
    have slipped -- an error in the flattering direction. `markout` detects this; this reports it
    rather than quietly taking the number.
    """
    if basis != "live":
        return {"value": UNMEASURED,
                "why": f"basis is {basis}: shadow R already carries the modelled cost, so any "
                       f"difference would be the cost model measured against itself"}
    try:
        from mt5desk import markout as _markout
        m = _markout.compute(_markout.load_jsonl(BASE / "data" / "order_intents.jsonl"),
                             _markout.load_jsonl(BASE / "data" / "live_ledger.jsonl"))
    except Exception as exc:                                      # noqa: BLE001
        return {"value": UNMEASURED, "why": f"markout unavailable: {type(exc).__name__}: {exc}"}

    if getattr(m, "mixed", False):
        return {"value": UNMEASURED, "why": m.why, "account_kind": m.account_kind}
    if not m.n_matched:
        return {"value": UNMEASURED, "why": m.why, "n_unfilled_intents": m.n_unfilled_intents,
                "n_unmatched_deals": m.n_unmatched_deals}
    return {
        "value": round(-float(m.mean_slip_r), 8),
        "mean_slip_r": round(float(m.mean_slip_r), 8),
        "median_slip_quote": round(float(m.median_slip_quote), 8),
        "worst_slip_quote": round(float(m.worst_slip_quote), 8),
        "edge_share": (round(float(m.edge_share), 6) if m.edge_share is not None else None),
        "n_matched_fills": int(m.n_matched),
        "n_unfilled_intents": int(m.n_unfilled_intents),
        "n_unmatched_deals": int(m.n_unmatched_deals),
        "account_kind": m.account_kind,
        "why": "requested versus filled price, per fill, joined by order ticket",
    }


def build(days: int = 30) -> dict[str, Any]:
    forecasts = load_forecasts(days)
    realized, basis = realized_daily()
    edge = _edge_term(forecasts, realized)
    disp = _dispersion_term(forecasts, realized)
    reg = _regime_term(forecasts)
    exe = _execution_term(basis)

    named = [float(t["value"]) for t in (edge, disp, exe) if isinstance(t.get("value"), float)]
    residual: Any = UNMEASURED
    if isinstance(edge.get("value"), float) and forecasts:
        # Total miss minus what the named terms account for. NEVER distributed into them.
        residual = round(float(edge["value"]) - sum(named[1:]), 8)

    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "window_days": days,
        "forecast_passes": len(forecasts),
        "realized_basis": basis,
        "sleeves_with_realized_evidence": len(realized),
        "terms": {"edge": edge, "correlation": disp, "execution": exe, "regime": reg},
        "residual": residual,
        "note": ("Every term reports UNMEASURED rather than zero when the evidence is absent. "
                 "Read the regime term FIRST: a sleeve that loses in the wrong regime has not "
                 "decayed, and retiring it would destroy an edge on a calendar accident."),
    }


def main() -> int:
    doc = build()
    print(f"forecast passes {doc['forecast_passes']}  basis {doc['realized_basis']}  "
          f"sleeves with realized evidence {doc['sleeves_with_realized_evidence']}")
    for name, t in doc["terms"].items():
        v = t.get("value")
        shown = v if isinstance(v, str) else f"{v:+.8f}"
        print(f"  {name:<12} {shown}")
        if t.get("why"):
            print(f"               {t['why']}")
        if t.get("reading"):
            print(f"               {t['reading']}")
    print(f"  {'residual':<12} {doc['residual']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"-> {OUT.relative_to(BASE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
