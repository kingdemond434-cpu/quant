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

THE GROWTH DECOMPOSITION (2026-09-04). The four error terms say which MODEL was wrong. The
growth decomposition asks the other question the principal keeps asking -- where did the growth
go -- and answers it in log-wealth per day under the two governance rules it exists to enforce:

    "Every risk reduction mechanism must prove that it increases robust forward E[log W]."
    "Every strong opportunity must be allowed to increase capital above normal when the
    evidence supports it."

Nine terms, each {value | UNMEASURED, basis, why}:

    ALPHA           the edge term above: what the sleeves did against what was expected
    SELECTION       E[log] of the FUNDED book minus an equal-weight book of every certified
                    sleeve at the same heat -- what choosing sleeves earned over not choosing
    STATE           the regime term above: how far the regime mix moved
    SIZING          the anti-timidity ledger. Realised total heat against the 20% floor and 30%
                    ceiling; when the book sat UNDER the floor, growth foregone is
                    (floor - realised) x expected_log_per_day / realised. A POSITIVE number is
                    the desk deploying less than the growth optimum, and it is charged as a
                    cost like any other, because timidity is a risk-reduction mechanism too
    DIVERSIFICATION nominal minus effective heat: the part of the nominal book that latent
                    factors, covariance and tail dependence say is one bet
    EXECUTION       the execution term above: fills against the cost model
    EXIT            the capture ratio: the share of each trade's peak the exit kept
    COST            modelled against measured slip from the learned fill surface
    VETO            the summed value of every filter and rail the desk has priced

The RESIDUAL stays reported and is never distributed into the named terms. Values read from
files that may be absent off-box (the allocator's proof, the fill surface, the exit accounts,
the rail ledgers) read UNMEASURED with the path named, so a missing artifact is a visible gap
rather than a zero.

THE WEEKLY TABLE, ENTRY, AND DEAD INFORMATION (2026-09-05).

    "Portfolio growth attribution: dlogW = Alpha + Selection + State + Sizing + Diversification
     + Execution + Exit + Costs + Veto, so every week you can answer what actually made us
     richer."                                                              -- the principal
    "Information attribution per data source: dElog_DataSource; kill dead information."

Three things were missing to make that a weekly answer rather than a daily diagnostic.

ENTRY. The nine terms price everything a trade does EXCEPT the moment it started. The desk has
that ledger and nothing read it: `reports/EXCURSIONS.json` carries each sleeve's median adverse
excursion, which is exactly what the entries paid before the thesis worked. It is a TENTH term
(`_entry_term`), and the reason it is not simply appended to the nine is in `weekly_table`: the
nine-term dict is a pinned contract, so the ten-term table lives in the weekly report.

THE IDENTITY, AND WHY IT DOES NOT CLOSE. `dlogW` is a measurable number -- the heat-weighted
realised return per scored day, from the forecast log's own books joined to the realised ledger.
Four of the ten terms are priced in log-wealth per day and can be subtracted from it; the rest
are priced in R, in heat, in fractions of price or as ratios, because that is the unit their
ledger actually keeps. Summing them anyway would be a decomposition that balances by changing
units mid-sum. So the report states the identity it CAN close, names every term it left out with
its unit and the reason, and calls the gap RESIDUAL -- reported, never distributed. A residual
this large is the honest measurement of how far the desk is from the principal's sentence, and
shrinking it means giving a term a log-wealth ledger, not moving a number.

INFORMATION ATTRIBUTION. `dElog_DataSource` per source, from the research P&L the desk already
computes: the expected log-wealth per day the source's certificates carry in the funded book,
against the trials it burned to get them. A source with trials and no growth is named DEAD
INFORMATION -- the report NAMES it; killing it is the bandit's and a person's decision.
"""
from __future__ import annotations

import json
import math
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
WEEKLY_OUT = BASE / "reports" / "GROWTH_ATTRIBUTION_WEEKLY.json"

#: Minimum scored days before a term is reported as a number rather than UNMEASURED. Below this
#: the decomposition is describing noise, and four confident numbers about noise is worse than
#: one honest refusal.
MIN_DAYS = 5
#: The weekly window the principal asked the question over, and the trailing window the same
#: table is repeated on so one quiet week cannot read as a trend.
WEEK_DAYS = 7
TRAILING_DAYS = 30
#: Trials a data source must have burned before "no growth" is a verdict rather than a cold arm.
#: Below it the source is UNMEASURED, which is what protects a new source from being killed for
#: being new (the same exploration floor the research bandit keeps).
MIN_SOURCE_TRIALS = 20
#: Measured trades a sleeve needs before its median excursion prices the entry.
MIN_ENTRY_TRADES = 10

UNMEASURED = "UNMEASURED"
DEAD_INFORMATION = "DEAD_INFORMATION"
PAYS = "PAYS"
#: The one unit that can be summed against the realised ledger. Every other unit on the table is
#: named on the term itself and kept OUT of the identity rather than converted by assumption.
LOGW = "log-wealth per day"

#: The utilisation floor and hard ceiling the sizing term reads the book against. These MIRROR
#: `heat_policy.HEAT_TARGET` / `HEAT_HARD_CEILING` (principal, 2026-09-02) and are read from
#: there when the policy module imports, so this ledger cannot judge the book against a bar the
#: policy no longer holds. They size nothing here: this is a reading, not a control.
HEAT_FLOOR = 0.20
HEAT_CEILING = 0.30

#: Every governance rule the decomposition is read under, verbatim, so the report carries them.
GOVERNANCE_RULES = (
    "Every risk reduction mechanism must prove that it increases robust forward E[log W].",
    "Every strong opportunity must be allowed to increase capital above normal when the "
    "evidence supports it.",
)


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
    except Exception as exc:
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


# --------------------------------------------------------------------------- growth decomposition
def _report(name: str) -> Path:
    """A desk report path resolved at CALL time, so a test can point BASE elsewhere."""
    return BASE / "reports" / name


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _num(v: Any) -> float | None:
    """A finite float or None. Strings, None, NaN and infinities are all 'not a number here'."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _gterm(value: Any, basis: str, why: str, **extra: Any) -> dict[str, Any]:
    return {"value": value, "basis": basis, "why": why, **extra}


def _heat_bars() -> tuple[float, float, str]:
    """The floor and ceiling from the policy module when it imports, else the mirrors."""
    try:
        from research import heat_policy as hp
        return float(hp.HEAT_TARGET), float(hp.HEAT_HARD_CEILING), "research.heat_policy"
    except Exception:
        return HEAT_FLOOR, HEAT_CEILING, "mirrored constants (heat_policy not importable here)"


def _lifted(term: dict[str, Any], basis: str, why: str) -> dict[str, Any]:
    """An existing error term re-read as a growth term, its own detail kept beside it."""
    return _gterm(term.get("value", UNMEASURED), basis, why if isinstance(term.get("value"), float)
                  else str(term.get("why") or why), **{k: v for k, v in term.items()
                                                       if k not in ("value", "why")})


def _score(v: Any) -> float | None:
    """A book score as mean log growth: the proof stores score_book dicts, the allocation
    artifact stores the number alone."""
    if isinstance(v, dict):
        return _num(v.get("mean_log_growth"))
    return _num(v)


def _selection_term() -> dict[str, Any]:
    """Funded book against an equal-weight book of every certified sleeve at the same heat.

    The contest the allocator already runs (`libs.portfolio.allocator_proof.contest`) scores
    both on ONE sampled world population at ONE total heat, which is the only comparison in
    which the difference is selection and not sizing. Read from the certificate first, then
    from the allocation artifact's copy of the proof scores.
    """
    for rel in ("ALLOCATOR_PROOF.json", "pf_allocation.json", "pf_allocator.json"):
        doc = _read_json(_report(rel))
        if not doc:
            continue
        scores = doc.get("scores") or (doc.get("proof") or {}).get("scores") or {}
        dyn, eq = _score(scores.get("dynamic")), _score(scores.get("equal_weight"))
        if dyn is None or eq is None:
            continue
        return _gterm(round(dyn - eq, 8), f"reports/{rel}: scores.dynamic vs scores.equal_weight",
                      "mean log growth per day of the funded book minus the equal-weight book "
                      "of every certified sleeve, same worlds, same total heat",
                      dynamic_log_per_day=round(dyn, 8), equal_weight_log_per_day=round(eq, 8),
                      total_heat_equalised=_num(doc.get("total_heat_equalised")),
                      proof_passed=doc.get("passed"))
    return _gterm(UNMEASURED, "reports/ALLOCATOR_PROOF.json (absent or without scores)",
                  "needs scores.dynamic.mean_log_growth and scores.equal_weight.mean_log_growth "
                  "from reports/ALLOCATOR_PROOF.json (or the proof scores copied into "
                  "reports/pf_allocation.json); no allocator pass has written them on this host")


def _sizing_term(forecasts: list[dict[str, Any]]) -> dict[str, Any]:
    """The anti-timidity ledger: growth foregone by holding the book under the floor.

        foregone = (heat_floor - heat_realised) x expected_log_per_day / heat_realised

    i.e. the growth the missing heat would have earned at the book's own growth per unit heat,
    linearised. POSITIVE means the desk deployed less than the growth optimum. A book over the
    ceiling is reported as an integrity breach, not as growth -- the ceiling is catastrophe
    containment and is never a target.
    """
    floor, ceiling, bars_basis = _heat_bars()
    pairs = [(h, g) for h, g in ((_num(f.get("total_heat")), _num(f.get("expected_log_per_day")))
                                 for f in forecasts) if h is not None and g is not None]
    if pairs:
        basis = (f"data/pf_forecast_log.jsonl ({len(pairs)} pass(es) in window); "
                 f"bars from {bars_basis}")
    else:
        doc = _read_json(_report("pf_allocation.json")) or {}
        h0 = _num((doc.get("heat") or {}).get("total"))
        g0 = _num((doc.get("growth") or {}).get("mean_log_per_day"))
        if h0 is None or g0 is None:
            return _gterm(UNMEASURED, "data/pf_forecast_log.jsonl / reports/pf_allocation.json",
                          "no allocator pass on this host: needs total_heat and "
                          "expected_log_per_day from data/pf_forecast_log.jsonl or heat.total "
                          "and growth.mean_log_per_day from reports/pf_allocation.json",
                          heat_floor=floor, heat_ceiling=ceiling)
        pairs = [(h0, g0)]
        basis = f"reports/pf_allocation.json (latest pass); bars from {bars_basis}"
    heat = statistics.fmean(h for h, _ in pairs)
    elog = statistics.fmean(g for _, g in pairs)
    if heat <= 1e-9:
        return _gterm(UNMEASURED, basis,
                      "the book held no heat, so expected growth per unit heat is undefined; "
                      "the shortfall to the floor is the whole floor",
                      heat_realised=round(heat, 6), heat_floor=floor, heat_ceiling=ceiling,
                      expected_log_per_day=round(elog, 8))
    per_heat = elog / heat
    under = heat < floor
    foregone = (floor - heat) * per_heat if under else 0.0
    if under:
        reading = (f"UNDER THE FLOOR: {heat:.2%} held against {floor:.0%}; the missing "
                   f"{floor - heat:.2%} of heat forewent {foregone:+.2e} log-wealth per day")
    elif heat > ceiling + 1e-9:
        reading = (f"ABOVE THE CEILING: {heat:.2%} against {ceiling:.0%} -- an integrity breach, "
                   f"not growth")
    else:
        reading = f"inside the band: {heat:.2%} held, floor {floor:.0%}, ceiling {ceiling:.0%}"
    return _gterm(round(foregone, 8), basis,
                  "(heat_floor - heat_realised) x expected_log_per_day / heat_realised when the "
                  "book sat under the floor, else 0; positive = deployed less than the growth "
                  "optimum (the anti-timidity ledger)",
                  heat_realised=round(heat, 6), heat_floor=floor, heat_ceiling=ceiling,
                  expected_log_per_day=round(elog, 8),
                  growth_per_unit_heat=round(per_heat, 8), under_floor=under,
                  above_ceiling=bool(heat > ceiling + 1e-9), reading=reading)


def _diversification_term() -> dict[str, Any]:
    """Nominal minus effective heat, from the allocator's latent-factor reading of its book.

    `libs.portfolio.latent_factors.effective` writes nominal, covariance, factor and tail heat
    and H_eff = max of the three. The difference is the heat the book only APPEARS to carry:
    20% across independent mechanisms is far less than 20% on one latent factor.
    """
    for rel in ("ALLOCATOR_PROOF.json", "pf_allocation.json", "pf_allocator.json"):
        doc = _read_json(_report(rel))
        eh = (doc or {}).get("effective_heat")
        if not isinstance(eh, dict):
            continue
        nominal, eff = _num(eh.get("nominal")), _num(eh.get("effective"))
        if nominal is None or eff is None:
            continue
        return _gterm(round(nominal - eff, 6), f"reports/{rel}: effective_heat",
                      "nominal heat minus H_eff = max(covariance, factor, tail) heat: the part "
                      "of the nominal book that is not independent bets",
                      nominal=nominal, effective=eff, n_eff=eh.get("n_eff"),
                      factor=_num(eh.get("factor")), covariance=_num(eh.get("covariance")),
                      tail=_num(eh.get("tail")), note=eh.get("note"))
    return _gterm(UNMEASURED, "reports/ALLOCATOR_PROOF.json / reports/pf_allocation.json",
                  "no effective_heat block (nominal, effective = max(covariance, factor, tail)) "
                  "in reports/ALLOCATOR_PROOF.json or reports/pf_allocation.json on this host")


def _exit_term() -> dict[str, Any]:
    """The capture ratio: the share of each trade's peak R that survived to the exit."""
    rel = "EXIT_ACCOUNTS.json"
    doc = _read_json(_report(rel))
    if doc is None:
        return _gterm(UNMEASURED, f"reports/{rel} (absent)",
                      f"reports/{rel} is not on this host; needs capture_ratio = realised R / "
                      "peak R (median over closed trades that had a peak)")
    cap = None
    where = ""
    for holder, label in ((doc, ""), (doc.get("summary"), "summary."),
                          (doc.get("exit"), "exit."), (doc.get("capture"), "capture.")):
        if not isinstance(holder, dict):
            continue
        for k in ("capture_ratio", "median_capture_ratio"):
            v = holder.get(k)
            cap = _num(v.get("value") if isinstance(v, dict) else v)
            if cap is not None:
                where = f"{label}{k}"
                break
        if cap is not None:
            break
    if cap is None:
        return _gterm(UNMEASURED, f"reports/{rel}",
                      f"reports/{rel} carries no capture_ratio / median_capture_ratio field")
    return _gterm(cap, f"reports/{rel}: {where}",
                  "share of the trade's peak R kept at exit; 1.0 = exit at the high, low = "
                  "the trailing rule gives back what the thesis earned",
                  n=doc.get("n") or doc.get("n_trades"))


def _cost_term() -> dict[str, Any]:
    """Modelled against measured slip from the learned fill surface, as fractions of price.

    SIGNED LIKE EXECUTION: negative when fills are worse than the model priced, because slip is
    a subtraction from edge. The surface today publishes its fitted weights and residual sd but
    not the pair this needs; until it does the term names exactly what is missing.
    """
    rel = "FILL_SURFACE.json"
    doc = _read_json(_report(rel))
    if doc is None:
        return _gterm(UNMEASURED, f"reports/{rel} (absent)",
                      f"reports/{rel} is not on this host; needs mean_slip_modelled and "
                      "mean_slip_measured (fractions of price)")
    modelled = _num(doc.get("mean_slip_modelled", doc.get("modelled_slip_frac")))
    measured = _num(doc.get("mean_slip_measured", doc.get("measured_slip_frac")))
    n_fills = doc.get("n_fills")
    if modelled is None or measured is None:
        return _gterm(UNMEASURED, f"reports/{rel}",
                      f"reports/{rel} carries the fitted surface (n_fills={n_fills}, "
                      f"slip_resid_sd={doc.get('slip_resid_sd')}) but no modelled-vs-measured "
                      "pair; needs mean_slip_modelled and mean_slip_measured (fractions of price)",
                      n_fills=n_fills, gaps=doc.get("gaps"))
    return _gterm(round(modelled - measured, 8), f"reports/{rel}: mean_slip_modelled vs "
                  "mean_slip_measured",
                  "modelled minus measured slip as a fraction of price; negative = fills worse "
                  "than the cost model priced",
                  mean_slip_modelled=modelled, mean_slip_measured=measured, n_fills=n_fills)


def _veto_term() -> dict[str, Any]:
    """The summed value of every priced filter and rail.

    Two ledgers, two units. MISSED_GROWTH prices rails in log-wealth per day and is the term's
    value; FILTER_VALUE prices vetoed brackets in R and is reported beside it, because R cannot
    be summed into log-wealth without the heat each trade carried. A rail whose verdict is
    UNMEASURED contributes nothing and is listed, never counted as zero.
    """
    fv = _read_json(_report("FILTER_VALUE.json")) or {}
    mg = _read_json(_report("MISSED_GROWTH.json")) or {}
    filters = fv.get("filters") if isinstance(fv.get("filters"), dict) else {}
    r_total = 0.0
    n_filters = 0
    for row in filters.values():
        v = _num((row or {}).get("filter_value_r")) if isinstance(row, dict) else None
        if v is not None:
            r_total += v
            n_filters += 1
    rails = mg.get("rails") if isinstance(mg.get("rails"), dict) else {}
    priced: dict[str, float] = {}
    unmeasured: list[str] = []
    for name, row in rails.items():
        if not isinstance(row, dict) or row.get("verdict") == UNMEASURED:
            unmeasured.append(str(name))
            continue
        v = _num(row.get("value_logw_per_day"))
        if v is None:
            per_veto, n = _num(row.get("value_logw_per_veto")), _num(row.get("n"))
            v = per_veto * n if per_veto is not None and n is not None else None
        if v is None:
            unmeasured.append(str(name))
            continue
        priced[str(name)] = v
    extra: dict[str, Any] = {
        "filter_value_r_total": (round(r_total, 6) if n_filters else None),
        "n_filters_priced": n_filters, "rails_priced": {k: round(v, 8) for k, v in priced.items()},
        "rails_unmeasured": sorted(unmeasured),
    }
    if not fv and not mg:
        return _gterm(UNMEASURED, "reports/FILTER_VALUE.json / reports/MISSED_GROWTH.json (absent)",
                      "neither reports/FILTER_VALUE.json nor reports/MISSED_GROWTH.json is on "
                      "this host", **extra)
    if not priced:
        return _gterm(UNMEASURED, "reports/MISSED_GROWTH.json rails / reports/FILTER_VALUE.json",
                      f"no rail carries a priced value yet ({len(unmeasured)} UNMEASURED) and "
                      f"{n_filters} filter(s) priced in R cannot be summed into log-wealth "
                      "without the heat per trade", **extra)
    return _gterm(round(sum(priced.values()), 8),
                  "reports/MISSED_GROWTH.json rails (log-wealth per day); "
                  "reports/FILTER_VALUE.json beside in R",
                  "sum of the priced rails' value in log-wealth per day: positive = the rails "
                  "earned their place, negative = they cost growth without proving themselves",
                  **extra)


def _entry_term() -> dict[str, Any]:
    """What the ENTRIES paid: the adverse excursion each one endured before the thesis worked.

    THE LEDGER EXISTED AND NOTHING READ IT. `excursions.py` has recorded median MAE per sleeve
    since it was written -- how far a trade went against the entry before it went anywhere -- and
    the growth decomposition had no entry term at all. That is the quantity: an entry a bar later
    at the same signal would have paid less of it, and a sleeve whose median MAE is 4R is not a
    sleeve with an exit problem.

    SIGNED AS A COST. Negative, like execution and cost, because excursion is a subtraction from
    what the entry could have had. It is NOT summed into the realised identity and says so: MAE
    is intra-trade drawdown, not a realised loss, and adding drawdown to realised return would
    charge the desk twice for trades that recovered.
    """
    rel = "EXCURSIONS.json"
    doc = _read_json(_report(rel))
    if doc is None:
        return _gterm(UNMEASURED, f"reports/{rel} (absent)",
                      f"reports/{rel} is not on this host; needs per-sleeve median_mae_r, which "
                      "is the R the entry gave away before the trade worked", unit="R per trade")
    sleeves = doc.get("sleeves") if isinstance(doc.get("sleeves"), dict) else {}
    rows: dict[str, float] = {}
    thin: list[str] = []
    for name, row in sleeves.items():
        if not isinstance(row, dict):
            continue
        mae, n = _num(row.get("median_mae_r")), _num(row.get("n"))
        if mae is None or n is None:
            continue
        if n < MIN_ENTRY_TRADES:
            thin.append(str(name))
            continue
        rows[str(name)] = mae
    if not rows:
        return _gterm(UNMEASURED, f"reports/{rel}",
                      f"no sleeve carries {MIN_ENTRY_TRADES}+ measured excursions "
                      f"({len(thin)} thin, {len(sleeves)} sleeve(s) on the ledger)",
                      unit="R per trade", thin_sleeves=sorted(thin))
    worst = dict(sorted(rows.items(), key=lambda kv: -kv[1])[:8])
    alloc = _read_json(_report("pf_allocation.json")) or {}
    book = {str(k): v for k, v in (alloc.get("book") or {}).items()}
    heat = {k: h for k in rows if (h := _num(book.get(k))) is not None and h > 0.0}
    if heat:
        value = -sum(heat[k] * rows[k] for k in heat)
        return _gterm(round(value, 8), f"reports/{rel}: median_mae_r x reports/pf_allocation.json "
                      "book heat",
                      "minus the heat-weighted median adverse excursion: the log-wealth each "
                      "entry gives away before the thesis works. NOT in the realised identity -- "
                      "intra-trade drawdown is not a realised loss",
                      unit="log-wealth of adverse excursion per trade", in_identity=False,
                      n_sleeves_funded=len(heat), n_sleeves_measured=len(rows),
                      worst_entries=worst, thin_sleeves=sorted(thin))
    return _gterm(round(-statistics.median(rows.values()), 8), f"reports/{rel}: median_mae_r",
                  "minus the median sleeve's median adverse excursion, in R: no funded book on "
                  "this host to weight it by heat, so this is the typical entry's cost and not "
                  "the book's",
                  unit="R per trade", in_identity=False, n_sleeves_measured=len(rows),
                  worst_entries=worst, thin_sleeves=sorted(thin),
                  why_unweighted="reports/pf_allocation.json carries no book heat here")


# --------------------------------------------------------------------------- the weekly table
def _stat(samples: list[float]) -> dict[str, Any]:
    """Mean, n and a 95% interval. The interval is the point: a term with n=5 and a term with
    n=200 are different evidence and the table has to show which is which."""
    n = len(samples)
    if not n:
        return {"value": UNMEASURED, "n": 0, "ci": None, "sd": None}
    mean = statistics.fmean(samples)
    sd = statistics.stdev(samples) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0
    return {"value": round(mean, 10), "n": n, "sd": round(sd, 10),
            "ci": [round(mean - 1.96 * se, 10), round(mean + 1.96 * se, 10)]}


def daily_book_growth(forecasts: list[dict[str, Any]],
                      realized: dict[str, dict[str, float]]) -> dict[str, float]:
    """Per scored day, sum_i h_i r_i -- the realised log-wealth the book actually made.

    THE LAST PASS OF A DAY SPEAKS FOR IT. The allocator can run several times in a day and each
    pass logs its book; summing them would count the same day's returns once per pass. The last
    book is the one the day ended on, which is the book that earned the day's R -- the same rule
    `_edge_term` already uses.
    """
    per_day: dict[str, float] = {}
    for f in forecasts:
        day = str(f["t"])[:10]
        book = {str(k): float(v) for k, v in (f.get("book") or {}).items()}
        got, seen = 0.0, False
        for name, h in book.items():
            r = realized.get(name, {}).get(day)
            if r is None:
                continue
            seen = True
            got += h * r
        if seen:
            per_day[day] = got
    return per_day


def per_sleeve(forecasts: list[dict[str, Any]], realized: dict[str, dict[str, float]],
               limit: int = 40) -> dict[str, Any]:
    """Which sleeve made the book richer, in the same unit as the book's own dlogW.

    Contribution is h_i x r_i averaged over the days the sleeve was FUNDED AND TRADED, so the
    per-sleeve rows sum to the book's dlogW over the days every sleeve was scored -- a sleeve
    that sat out is not charged with the days it did not hold heat.
    """
    contrib: dict[str, list[float]] = defaultdict(list)
    heats: dict[str, list[float]] = defaultdict(list)
    for f in forecasts:
        day = str(f["t"])[:10]
        for name, h in (f.get("book") or {}).items():
            r = realized.get(str(name), {}).get(day)
            hv = _num(h)
            if r is None or hv is None:
                continue
            contrib[str(name)].append(hv * r)
            heats[str(name)].append(hv)
    if not contrib:
        return {"value": UNMEASURED, "n_sleeves": 0,
                "why": "no forecast book joins a realised day: nothing to attribute per sleeve"}
    rows = {}
    for name, vals in contrib.items():
        st = _stat(vals)
        rows[name] = {**st, "mean_heat": round(statistics.fmean(heats[name]), 8),
                      "mean_r": round(statistics.fmean(v / h for v, h in
                                                       zip(vals, heats[name], strict=True)
                                                       if h), 8) if any(heats[name]) else None}
    ordered = sorted(rows.items(), key=lambda kv: -(kv[1]["value"] if
                                                    isinstance(kv[1]["value"], float) else 0.0))
    return {"n_sleeves": len(rows), "unit": LOGW,
            "sleeves": dict(ordered[:limit]),
            "best": [k for k, _ in ordered[:5]], "worst": [k for k, _ in ordered[-5:]],
            "why": ("mean over the days the sleeve was funded and traded of heat x realised R; "
                    f"showing the {min(limit, len(rows))} largest of {len(rows)}")}


def information_attribution() -> dict[str, Any]:
    """dElog_DataSource per source, and the ones that are DEAD INFORMATION.

    THE NUMBER ALREADY EXISTS. `research_pnl.py` attributes the allocator's own expected growth
    to the source each funded certificate came from, and counts the trials that source burned.
    That IS dElog per data source; it had no reader that named the dead ones. A source with
    trials past the exploration floor and no growth in the funded book is not "cold", it is
    information the desk paid for and is not being made richer by.

    KILLING IS NOT DONE HERE. The bandit already shrinks a cold arm's budget; this names the
    source, its growth, its spend and its ROI so a person or the bandit can act on the number.
    """
    rel = "RESEARCH_PNL.json"
    doc = _read_json(_report(rel))
    if doc is None:
        return {"value": UNMEASURED, "basis": f"reports/{rel} (absent)",
                "why": f"reports/{rel} is not on this host; it is where dElog per source lives",
                "unit": LOGW, "n_sources": 0, "sources": {}, "dead_information": [],
                "pays": [], "unmeasured": [], "unattributed_growth_per_day": None,
                "rule": (f"dElog_DataSource <= 0 with >= {MIN_SOURCE_TRIALS} trials is DEAD "
                         "INFORMATION; no source ledger on this host to judge")}
    sources = doc.get("sources") if isinstance(doc.get("sources"), dict) else {}
    rows: dict[str, Any] = {}
    dead: list[str] = []
    for name, c in sorted(sources.items()):
        if not isinstance(c, dict):
            continue
        growth = _num(c.get("growth_per_day"))
        trials = int(_num(c.get("trials")) or 0)
        cost = _num(c.get("cost_units")) or 0.0
        if growth is None or trials < MIN_SOURCE_TRIALS:
            verdict, why = UNMEASURED, (f"{trials} trial(s), need {MIN_SOURCE_TRIALS} before "
                                        "'no growth' is a verdict rather than a cold start")
        elif growth > 0.0:
            verdict, why = PAYS, ""
        else:
            verdict = DEAD_INFORMATION
            why = (f"{trials} trial(s) burned and the funded book carries no growth from this "
                   "source over its whole history")
            dead.append(str(name))
        rows[str(name)] = {
            "delta_elogw_per_day": (None if growth is None else round(growth, 10)),
            "unit": LOGW, "arm": c.get("arm"), "trials": trials,
            "certified": int(_num(c.get("certified")) or 0),
            "cost_units": round(cost, 2),
            "roi_growth_per_cost_unit": (round(growth / cost, 12)
                                         if growth is not None and cost else None),
            "verdict": verdict, "why": why}
    return {
        "basis": f"reports/{rel}: sources[*].growth_per_day, trials, cost_units",
        "unit": LOGW, "n_sources": len(rows), "sources": rows,
        "dead_information": sorted(dead),
        "pays": sorted(k for k, v in rows.items() if v["verdict"] == PAYS),
        "unmeasured": sorted(k for k, v in rows.items() if v["verdict"] == UNMEASURED),
        "unattributed_growth_per_day": _num(doc.get("unattributed_growth_per_day")),
        "rule": (f"dElog_DataSource <= 0 with >= {MIN_SOURCE_TRIALS} trials is DEAD INFORMATION. "
                 "This NAMES it; the research bandit's budget and a person do the killing."),
    }


def weekly_table(days: int = WEEK_DAYS) -> dict[str, Any]:
    """"What actually made us richer" over one window: ten terms, n, CI, and an honest residual.

    THE IDENTITY IS STATED, NOT FORCED. Only the terms whose ledger prices them in log-wealth per
    day are subtracted from the realised number; the rest carry their own unit and `in_identity`
    is False with the reason. The gap is RESIDUAL, reported and never distributed -- a residual
    folded into the named terms is how a decomposition becomes a story (the rule this file has
    kept since it was written).
    """
    forecasts = load_forecasts(days)
    realized, basis = realized_daily()
    edge = _edge_term(forecasts, realized)
    reg = _regime_term(forecasts)
    exe = _execution_term(basis)
    gd = growth_decomposition(forecasts, edge, reg, exe, UNMEASURED)

    per_day = daily_book_growth(forecasts, realized)
    dlogw = {**_stat(sorted(per_day.values())), "basis": basis,
             "why": ("mean over scored days of sum_i heat_i x realised R_i, from the forecast "
                     "log's own books joined to the realised ledger")}
    if not per_day:
        dlogw["why"] = ("no forecast book joins a realised day on this host: the ledger's own "
                        "dlogW is UNMEASURED, so nothing can be checked against it")

    #: Units per term, from the ledger each one actually reads. Anything not in log-wealth per
    #: day stays OUT of the identity: converting it would be inventing an exchange rate.
    units = {"alpha": LOGW, "selection": LOGW, "state": "regime total variation",
             "sizing": LOGW, "diversification": "heat", "execution": "R per fill",
             "exit": "capture ratio", "cost": "fraction of price", "veto": LOGW,
             "entry": None}
    terms: dict[str, Any] = {}
    for name in ("alpha", "selection", "state", "sizing", "diversification", "entry",
                 "execution", "exit", "cost", "veto"):
        t = dict(_entry_term() if name == "entry" else gd["terms"][name])
        unit = t.get("unit") or units[name] or LOGW
        in_identity = bool(t.get("in_identity", unit == LOGW)) and isinstance(t.get("value"),
                                                                             float)
        t.update({"unit": unit, "in_identity": in_identity})
        if not in_identity and isinstance(t.get("value"), float):
            t["out_of_identity_why"] = (f"priced in {unit}; no measured exchange rate to "
                                        "log-wealth per day exists on this desk, and inventing "
                                        "one would balance the sum by changing units mid-sum")
        # Every term's ledger counts its own evidence under its own name; the table needs ONE
        # column, so the count is resolved here rather than leaving the reader to know which
        # field each ledger uses. None stays None -- an absent count is not a zero.
        if t.get("n") is None:
            for key in ("scored_days", "n_matched_fills", "n_fills", "n_sleeves_funded",
                        "n_sleeves_measured", "n_filters_priced"):
                if t.get(key) is not None:
                    t["n"], t["n_basis"] = int(t[key]), key
                    break
            else:
                t["n"], t["n_basis"] = None, "the term's ledger carries no count"
        terms[name] = t

    summed = {k: float(t["value"]) for k, t in terms.items() if t["in_identity"]}
    total = round(sum(summed.values()), 10)
    closes = isinstance(dlogw["value"], float)
    residual: Any = round(float(dlogw["value"]) - total, 10) if closes else UNMEASURED
    # The two reasons a term sits outside the identity are DIFFERENT and must not read alike: a
    # measured term in another unit is a conversion the desk does not have, an UNMEASURED one is
    # a ledger the desk does not have. Folding them into one list would hide which is which.
    other_unit = {k: t["unit"] for k, t in terms.items()
                  if not t["in_identity"] and isinstance(t.get("value"), float)}
    no_ledger = sorted(k for k, t in terms.items() if not isinstance(t.get("value"), float))
    identity = {
        "rule": ("dlogW_realised = (terms priced in log-wealth per day) + RESIDUAL. The residual "
                 "is REPORTED and never distributed into the named terms."),
        "dlogw_per_day": dlogw["value"], "terms_in_identity": sorted(summed),
        "terms_summed_logw_per_day": total,
        "terms_out_of_identity": {k: t["unit"] for k, t in terms.items() if not t["in_identity"]},
        "measured_in_another_unit": other_unit, "unmeasured_terms": no_ledger,
        "residual": {
            "name": "UNDISTRIBUTED", "value": residual,
            "why": ("everything the log-wealth terms do not account for: the book's own EXPECTED "
                    "growth (alpha prices only realised minus expected); "
                    + (", ".join(f"{k} ({u})" for k, u in other_unit.items())
                       or "no measured term in another unit")
                    + "; and " + (", ".join(no_ledger) or "no term")
                    + " with no ledger on this host. Shrinking it means giving one of those "
                      "terms a log-wealth ledger, not moving a number.")},
        "closes": closes, "tolerance": 1e-9,
    }
    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "window_days": days, "forecast_passes": len(forecasts),
        "scored_days": dlogw["n"], "realised_basis": basis,
        "rules": list(GOVERNANCE_RULES),
        "dlogw_per_day": dlogw, "terms": terms, "identity": identity,
        "measured": sorted(k for k, t in terms.items() if isinstance(t.get("value"), float)),
        "unmeasured": sorted(k for k, t in terms.items() if not isinstance(t.get("value"), float)),
        "per_sleeve": per_sleeve(forecasts, realized),
        "information": information_attribution(),
        "reading": ("the answer to 'what made us richer this week'. A term that reads UNMEASURED "
                    "has no ledger on this host and is NOT a zero; the residual is what the "
                    "measured terms leave unexplained and is never distributed into them."),
    }


def growth_decomposition(forecasts: list[dict[str, Any]], edge: dict[str, Any],
                         reg: dict[str, Any], exe: dict[str, Any],
                         residual: Any) -> dict[str, Any]:
    """The nine growth terms plus the residual, which is reported and never distributed."""
    terms = {
        "alpha": _lifted(edge, "terms.edge", "heat-weighted realised minus expected per-sleeve "
                         "growth: what the edges did"),
        "selection": _selection_term(),
        "state": _lifted(reg, "terms.regime", "total-variation drift of the regime mix across "
                         "the window: how far the state moved from the forecast's"),
        "sizing": _sizing_term(forecasts),
        "diversification": _diversification_term(),
        "execution": _lifted(exe, "terms.execution", "realised minus modelled fill cost per unit "
                             "heat, live fills only"),
        "exit": _exit_term(),
        "cost": _cost_term(),
        "veto": _veto_term(),
    }
    measured = {k: t["value"] for k, t in terms.items() if isinstance(t.get("value"), float)}
    return {
        "rules": list(GOVERNANCE_RULES),
        "unit": "log-wealth per day unless a term's basis says otherwise (exit is a ratio, "
                "diversification is heat)",
        "terms": terms,
        "residual": {"value": residual, "why": "the total miss the named terms do not account "
                                              "for; reported, never distributed"},
        "measured": sorted(measured),
        "unmeasured": sorted(k for k in terms if k not in measured),
        "reading": ("read SIZING with the second rule in mind: a positive number is growth the "
                    "desk declined, and it is charged like any other cost"),
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
        "growth_decomposition": growth_decomposition(forecasts, edge, reg, exe, residual),
        # The tenth term and the two machine-readable tables, on the daily artifact as well as
        # the weekly one so a consumer needs exactly one file (see `run`).
        "entry": _entry_term(),
        "dlogw_per_day": {**_stat(sorted(daily_book_growth(forecasts, realized).values())),
                          "basis": basis, "unit": LOGW},
        "per_sleeve": per_sleeve(forecasts, realized),
        "information": information_attribution(),
        "note": ("Every term reports UNMEASURED rather than zero when the evidence is absent. "
                 "Read the regime term FIRST: a sleeve that loses in the wrong regime has not "
                 "decayed, and retiring it would destroy an edge on a calendar accident."),
    }


def run(days: int = TRAILING_DAYS, week_days: int = WEEK_DAYS,
        write: bool = True) -> dict[str, Any]:
    """The scheduled pass: the daily artifact, plus the weekly table and its trailing companion.

    IDEMPOTENT BY CONSTRUCTION. Both artifacts are whole-file rewrites of quantities derived from
    append-only ledgers this pass does not touch, so running it twice in a day changes nothing
    but the timestamp -- which is what let `daily_cycle` adopt it without a stamp of its own.

    TWO WINDOWS, ONE TABLE. The weekly window answers the principal's question; the trailing one
    is the same table over `days` so a single quiet week cannot read as a trend, and so a term
    that is UNMEASURED at n=7 but measured at n=30 is visibly the SAME term rather than two.
    """
    doc = build(days)
    weekly = weekly_table(week_days)
    weekly["trailing"] = weekly_table(days)
    if write:
        for path, payload in ((_report("allocator_attribution.json"), doc),
                              (_report("GROWTH_ATTRIBUTION_WEEKLY.json"), weekly)):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    return {"window_days": days, "week_days": week_days,
            "realised_basis": weekly["realised_basis"], "scored_days": weekly["scored_days"],
            "measured": weekly["measured"], "unmeasured": weekly["unmeasured"],
            "dlogw_per_day": weekly["dlogw_per_day"]["value"],
            "residual": weekly["identity"]["residual"]["value"],
            "dead_information": weekly["information"]["dead_information"],
            "n_sleeves_attributed": weekly["per_sleeve"].get("n_sleeves", 0),
            "weekly": weekly, "daily": doc}


def _print_weekly(w: dict[str, Any]) -> None:
    ident = w["identity"]
    print(f"WHAT MADE US RICHER  window {w['window_days']}d  scored days {w['scored_days']}  "
          f"basis {w['realised_basis']}  dlogW/day {w['dlogw_per_day']['value']}")
    for name, t in w["terms"].items():
        v = t.get("value")
        shown = v if isinstance(v, str) else f"{v:+.8f}"
        mark = "=" if t["in_identity"] else " "
        print(f" {mark}{name:<16}{shown:>16}  [{t['unit']}]  n={t.get('n')}  ci={t.get('ci')}")
        if isinstance(v, str) and t.get("why"):
            print(f"                  {t['why']}")
    print(f"  {'RESIDUAL':<16}{ident['residual']['value']!s:>16}  "
          f"[{LOGW}]  {ident['residual']['name']}")
    info = w["information"]
    print(f"information: {info['n_sources']} source(s), dead={info['dead_information']}")
    ps = w["per_sleeve"]
    if ps.get("n_sleeves"):
        print(f"per sleeve: best={ps['best']}  worst={ps['worst']}")


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
    gd = doc["growth_decomposition"]
    print(f"growth decomposition  measured {len(gd['measured'])}  "
          f"unmeasured {len(gd['unmeasured'])}")
    for name, t in gd["terms"].items():
        v = t.get("value")
        shown = v if isinstance(v, str) else f"{v:+.8f}"
        print(f"  {name:<15} {shown}   [{t.get('basis')}]")
        if isinstance(v, str) and t.get("why"):
            print(f"                  {t['why']}")
        if t.get("reading"):
            print(f"                  {t['reading']}")
    out = run()
    _print_weekly(out["weekly"])
    for p in (OUT, WEEKLY_OUT):
        print(f"-> {p.relative_to(BASE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
