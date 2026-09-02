#!/usr/bin/env python3
"""THE CAPITAL BRAIN -- robust posterior E[log W] over every validated edge, on many clocks.

    "At every moment, identify and allocate to the combination of currently available validated
     independent edges that maximizes robust expected log-wealth after costs and uncertainty.
     Never force a trade when the robust marginal Elog is non-positive; instead feed that
     opportunity gap back into research."                          -- the principal, 2026-09-02

WHAT THIS IS. The desk's allocation decision, made from evidence and written to
`reports/pf_allocation.json`. It solves for PER-SLEEVE HEAT, not weights, so the answer to "how
much in total" and "on what" is one optimisation instead of a constant and an optimisation. It
runs on three clocks:

    --mode fast     ~5 min   reuse the cached scenario population, re-solve the book
    --mode normal  ~15 min   rebuild evidence, re-solve, re-run the no-trade filter
    --mode heavy    hourly   resample the whole world population, re-measure the growth curve,
                             re-certify the utilisation target

WHY THREE. The expensive part is the scenario population (posterior draws x regimes x crisis
overlays x execution draws), not the optimisation -- measured 2026-09-02, sampling 256 worlds
over 109 sleeves costs 0.3 s and the solve 3 s, while ASSEMBLING the evidence costs 104 s. So the
cheap loops reuse the cache and the heavy loop earns it. Nothing here is throttled to protect
compute; it is split because the inputs genuinely change on different clocks.

WHAT IT DOES NOT DO. It places no orders and moves no capital. It writes the book the gateway
reads and the marginal ranking `cap_by_heat` trims by. Arming stays a human act
(`data/PF_ALLOCATOR_ARMED`); until that file exists this is a measurement the desk can compare
against what it is actually doing -- which is itself the finding, because the two have never been
compared.

THE NO-TRADE REGION. `--mode` says how often it RECOMPUTES, never how often it TRADES. A
recomputation that wants less turnover than it is worth returns NO CHANGE, so the allocator can
run every 15 minutes and move the book twice a day.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import (  # noqa: E402
    AllocationResult,
    SleeveEvidence,
    WorldConfig,
    Worlds,
    optimise,
    sample_worlds,
)
from research.heat_policy import (  # noqa: E402
    HEAT_HARD_CEILING,
    HEAT_TARGET,
    per_sleeve_bounds,
    resolve,
)

OUT = BASE / "reports" / "pf_allocation.json"
DONE = BASE / "reports" / "DONE_pf_allocation"
CACHE = BASE / "data" / "pf_allocator_cache"
ARMED = BASE / "data" / "PF_ALLOCATOR_ARMED"

#: How stale the assembled daily-R matrix may be before a `normal` pass rebuilds it. The matrix
#: changes when a new certificate lands or a sleeve accumulates bars -- both hourly events -- so
#: an hour is the honest refresh, and the heavy clock rebuilds unconditionally anyway.
EVIDENCE_MAX_AGE_S = 3600

#: Heat curve grid for certification. Spans the free optimum through the hard ceiling so the
#: peak is bracketed rather than assumed.
CURVE_GRID = (0.02, 0.04, 0.06, 0.08, 0.10, 0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.275, 0.30)

#: Round-trip execution cost charged against a unit of heat moved, in account fraction. Turnover
#: below the growth it buys is not an improvement, and this is the price that decides.
TURNOVER_COST_R = 0.06
#: Days of growth the rebalance is expected to earn before the next one supersedes it. Short on
#: purpose: a rebalance justified only by a month of undisturbed holding is not justified.
NO_TRADE_HORIZON_DAYS = 5.0

#: Regime-mixture bounds. No regime the desk has enough history for is ever assigned zero worlds
#: (MIN), and no regime may own more than MAX of the population however certain the classifier
#: sounds. See `regime_state` for the measurement that made both necessary.
REGIME_MIN_SHARE = 0.08
REGIME_MAX_SHARE = 0.60


def _log(msg: str) -> None:
    print(f"[{datetime.now(UTC):%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------------------------------
# EVIDENCE
# ---------------------------------------------------------------------------------------

def build_evidence(*, force: bool = False) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """The daily-R matrix for every priced sleeve, plus forward days per sleeve.

    Cached to parquet because assembling it costs ~104 s and the 5-minute clock cannot pay that.
    A STALE CACHE IS DECLARED, never silently used as fresh: the artifact carries the cache age so
    a reader can tell a live allocation from one standing on yesterday's matrix (L1.28a).
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    mat = CACHE / "daily_r.parquet"
    age = time.time() - mat.stat().st_mtime if mat.exists() else float("inf")
    if force or age > EVIDENCE_MAX_AGE_S or not mat.exists():
        from research.portfolio_projection import (
            build_daily,
            build_sleeves,
            h18_survivor_sleeves,
        )
        _log("assembling evidence (backtest daily-R over gold book + hunt survivors)")
        sleeves = build_sleeves()
        h18, excluded = h18_survivor_sleeves()
        sleeves += h18
        if excluded:
            _log(f"excluded {len(excluded)} survivor(s) fail-closed")
        daily = build_daily(sleeves)
        daily.index = [str(x) for x in daily.index]
        daily.to_parquet(mat)
        _log(f"evidence rebuilt: {daily.shape[0]} days x {daily.shape[1]} sleeves")
    else:
        daily = pd.read_parquet(mat)
        _log(f"evidence from cache ({age / 60:.0f} min old): {daily.shape}")

    forward: dict[str, dict[str, float]] = {}
    try:
        from research.portfolio_evidence import daily_series
        forward = daily_series()
    except Exception as exc:
        _log(f"forward evidence unavailable ({type(exc).__name__}); backtest basis only")
    return daily, forward


def live_days_by_sleeve() -> dict[str, int]:
    """Days of REAL-CAPITAL evidence per sleeve, from the gateway's live ledger.

    Live days outrank forward days outrank backtest days in `_posterior_mu`, so this is what lets
    a sleeve earn size by trading rather than by having been fitted. The ledger was empty until
    2026-09-01 (the gateway required a broker-rewritable comment prefix), so an empty answer here
    is expected for now and is reported as zero live evidence rather than hidden.
    """
    path = BASE / "data" / "live_ledger.jsonl"
    if not path.exists():
        return {}
    days: dict[str, set[str]] = {}
    for line in path.read_text("utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        name, when = str(row.get("sleeve") or ""), str(row.get("close_time") or "")[:10]
        if name and when:
            days.setdefault(name, set()).add(when)
    return {k: len(v) for k, v in days.items()}


def regime_state(daily: pd.DataFrame) -> tuple[tuple[str, ...], tuple[tuple[str, float], ...]]:
    """Per-day regime label over the matrix's own clock, and today's regime probabilities.

    PROBABILITIES, NOT A LABEL. `libs/regime/engine.py` already cross-checks an HMM against a GMM
    and dampens confidence on disagreement; what the allocator needs from it is the POSTERIOR, so
    a book is scored against the mix of worlds the desk believes it is in rather than switched
    wholesale into whichever state the classifier called this minute. A classifier that flickers
    then costs a little weight, not the whole book.

    Fitted on XAUUSD daily closes -- the desk's dominant instrument and the one every sleeve's
    session structure is defined against. Returns empty tuples when the engine cannot fit, in
    which case `sample_worlds` draws unconditioned worlds and says so in the artifact.
    """
    try:
        from libs.regime.engine import RegimeEngine

        px = pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet")
        col = next((c for c in ("close", "Close", "c") if c in px.columns), None)
        tcol = next((c for c in ("time", "Time", "datetime") if c in px.columns), None)
        if col is None:
            raise KeyError("no close column on XAUUSD_H1")
        idx = pd.to_datetime(px[tcol] if tcol else px.index, utc=True, errors="coerce")
        close = pd.Series(px[col].to_numpy(dtype=float), index=idx).dropna()
        close = close.groupby(close.index.date).last()
        if close.size < 250:
            raise ValueError(f"only {close.size} daily closes; refusing to fit a regime on that")

        eng = RegimeEngine().fit(close)
        lab = {j: str(ch["label"]) for j, ch in eng.hmm_char.items()}
        by_day = {str(d): lab[int(j)] for d, j in zip(close.index, eng.hmm_states, strict=True)}
        labels = tuple(by_day.get(str(d)[:10], "") for d in daily.index)

        # Today's probabilities: the last filtered posterior, summed onto LABELS rather than
        # latent state indices, because two states can carry the same economic label.
        post = eng.posteriors[-1]
        raw: dict[str, float] = {}
        for j, pj in enumerate(post):
            raw[lab[int(j)]] = raw.get(lab[int(j)], 0.0) + float(pj)

        # A FILTER POSTERIOR OF 1.0 IS A HARD SWITCH WEARING A PROBABILITY'S CLOTHES, and this
        # engine produces them: measured 2026-09-02 it returned bull/high_vol at 100.0%, which
        # sent every sampled world into one regime's days. The principal's instruction was
        # explicit -- "don't make the regime classifier binary" -- so the raw posterior is
        # tempered three ways before the allocator is allowed to believe it:
        #
        #   1. BLENDED with the empirical frequency of each regime over history, weighted by the
        #      engine's OWN confidence (which it already dampens on HMM/GMM disagreement). A
        #      confident classifier keeps its posterior; an uncertain one falls back to how often
        #      each regime actually occurs.
        #   2. FLOORED, so no regime with enough history is ever assigned zero worlds. The desk
        #      is never certain it is not in a regime.
        #   3. CAPPED, so no single regime may own more than REGIME_MAX_SHARE of the worlds. This
        #      is the one that stops a 100% posterior from becoming a 100% world population.
        freq: dict[str, float] = {}
        for v in by_day.values():
            freq[v] = freq.get(v, 0.0) + 1.0
        tot = sum(freq.values()) or 1.0
        freq = {k: v / tot for k, v in freq.items()}
        conf = float(str(eng.current().get("confidence") or 0.0))
        keys = sorted(set(raw) | set(freq))
        probs = {k: conf * raw.get(k, 0.0) + (1.0 - conf) * freq.get(k, 0.0) for k in keys}
        probs = {k: max(v, REGIME_MIN_SHARE) for k, v in probs.items()}
        tot = sum(probs.values()) or 1.0
        probs = {k: v / tot for k, v in probs.items()}
        if max(probs.values()) > REGIME_MAX_SHARE:
            top = max(probs, key=lambda k: probs[k])
            spill = probs[top] - REGIME_MAX_SHARE
            rest = sum(v for k, v in probs.items() if k != top) or 1.0
            probs = {k: (REGIME_MAX_SHARE if k == top else v + spill * v / rest)
                     for k, v in probs.items()}
        _log(f"regime raw={ {k: round(v, 3) for k, v in raw.items()} } conf={conf:.2f} "
             f"-> used={ {k: round(v, 3) for k, v in probs.items()} }")
        covered = sum(1 for x in labels if x)
        if covered < 0.5 * len(labels):
            _log(f"regime labels cover only {covered}/{len(labels)} matrix days; unconditioned")
            return (), ()
        return labels, tuple(sorted(probs.items(), key=lambda kv: -kv[1]))
    except Exception as exc:
        _log(f"regime engine unavailable ({type(exc).__name__}: {exc}); worlds are unconditioned")
    return (), ()


def sleeve_evidence(daily: pd.DataFrame, forward: dict[str, dict[str, float]],
                    live: dict[str, int]) -> list[SleeveEvidence]:
    """Fold backtest, forward and live evidence into one record per sleeve.

    Forward days are APPENDED to the backtest series, not averaged into it: they are additional
    observations of the same sleeve, and the posterior weights them 4x (live 12x) precisely
    because they are the only ones the sleeve could not have been selected on.
    """
    out: list[SleeveEvidence] = []
    for name in daily.columns:
        hist = daily[name].fillna(0.0).to_numpy(dtype=float)
        fwd = forward.get(str(name), {})
        if fwd:
            hist = np.concatenate([hist, np.array(list(fwd.values()), dtype=float)])
        fam = str(name).split("_")[0]
        out.append(SleeveEvidence(
            name=str(name), daily_r=hist, family=fam, symbol=fam,
            forward_days=len(fwd), live_days=int(live.get(str(name), 0)),
            # Cost LEVEL is already inside the replayed R multiples (Costs.from_symbol at the
            # honest 2x baseline); this is the per-trade scale used to size the UNCERTAINTY
            # around it, never a second charge.
            cost_r=0.05,
        ))
    return out


def worst_dd_r(daily: pd.DataFrame) -> dict[str, float]:
    """Each sleeve's worst peak-to-trough drawdown in R -- the input to its per-sleeve bound."""
    out: dict[str, float] = {}
    for name in daily.columns:
        eq = daily[name].fillna(0.0).cumsum().to_numpy(dtype=float)
        if eq.size == 0:
            out[str(name)] = 0.0
            continue
        out[str(name)] = float(np.maximum.accumulate(eq).max() - eq.min()) if eq.size else 0.0
        dd = np.maximum.accumulate(eq) - eq
        out[str(name)] = float(dd.max()) if dd.size else 0.0
    return out


# ---------------------------------------------------------------------------------------
# SOLVE
# ---------------------------------------------------------------------------------------

def growth_curve(ev: list[SleeveEvidence], worlds: Worlds, bounds: dict[str, float],
                 cfg: WorldConfig) -> dict[float, float]:
    """Mean log growth of the OPTIMALLY COMPOSED book at each total heat on the grid.

    This is the curve `heat_policy.certify` reads, and it must be measured with the same
    per-sleeve bounds the desk will actually run: without them the optimiser answers the mandate
    by parking heat in the flattest sleeve it can find, and the curve comes out flat because the
    surplus was never really deployed. A certification measured on an unconstrained solve
    certifies a book nobody would run.
    """
    curve: dict[float, float] = {}
    for h in CURVE_GRID:
        if h > HEAT_HARD_CEILING:
            continue
        ub = {k: min(v, h) for k, v in bounds.items()}
        if sum(ub.values()) < h:
            continue                     # bounds cannot fund this heat; not a growth finding
        try:
            r = optimise(ev, hard_cap=HEAT_HARD_CEILING, target=h, cfg=cfg, worlds=worlds,
                         max_per_sleeve=ub)
        except ValueError:
            continue
        if math.isfinite(r.mean_log_growth):
            curve[h] = r.mean_log_growth
    return curve


def no_trade(current: dict[str, float], proposed: dict[str, float],
             gain_per_day: float) -> dict[str, Any]:
    """Is the move worth its own cost? Returns the verdict and the arithmetic behind it.

    "Don't rebalance simply because the optimizer ran." Turnover is charged at a round trip on
    every unit of heat that moves, and the move only happens when the growth it buys over
    `NO_TRADE_HORIZON_DAYS` exceeds that. This is what lets the allocator recompute every fifteen
    minutes and still trade twice a day.
    """
    names = set(current) | set(proposed)
    moved = {n: proposed.get(n, 0.0) - current.get(n, 0.0) for n in names}
    turnover = 0.5 * sum(abs(v) for v in moved.values())
    cost = turnover * TURNOVER_COST_R
    benefit = max(gain_per_day, 0.0) * NO_TRADE_HORIZON_DAYS
    go = benefit > cost
    return {
        "verdict": "REBALANCE" if go else "NO CHANGE",
        "turnover": round(turnover, 6),
        "cost": round(cost, 8),
        "benefit_over_horizon": round(benefit, 8),
        "horizon_days": NO_TRADE_HORIZON_DAYS,
        "largest_moves": dict(sorted(((k, round(v, 5)) for k, v in moved.items() if abs(v) > 1e-5),
                                     key=lambda kv: -abs(kv[1]))[:12]),
    }


def current_book() -> dict[str, float]:
    """What the desk is running now, in heat -- the baseline the no-trade filter measures against.

    Read from the previous allocation when there is one, else from the gateway's own sleeve set
    priced at Q_OPT. NOT from a list in this file: a second opinion about what is live is the
    exact drift this whole module exists to remove.
    """
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text("utf-8"))
            book = prev.get("book")
            if isinstance(book, dict) and book:
                return {str(k): float(v) for k, v in book.items()}
        except (OSError, ValueError):
            pass
    try:
        from mt5desk.gateway import sleeve_set
        from mt5desk.gateway_config_fallback import Q_OPT
        return {str(s["name"]): float(Q_OPT) for s in sleeve_set()}
    except Exception:
        try:
            from mt5desk.gateway_config_fallback import Q_OPT

            from research.promoter import GOLD_SLEEVE_NAMES, _load_gold_retired
            retired = set(_load_gold_retired())
            return {n: float(Q_OPT) for n in GOLD_SLEEVE_NAMES if n not in retired}
        except Exception:
            return {}


def opportunity(free: AllocationResult, book: dict[str, float],
                target: float) -> dict[str, Any]:
    """Opportunity density and the heat gap -- what research is asked to go and find.

    OD = sum of POSITIVE marginal dE[log W] across the eligible library. High OD means many
    independent things are worth betting on and a large budget is fillable; low OD means the
    honest answer to "why is the book not at target" is that the world is not currently offering
    twenty percent of independent edge, and that is a RESEARCH REQUEST, not a risk decision.

    The gap is expressed by session and family so the crawler has somewhere to point: a gap that
    says "4% unfilled" is a number, and one that says "4% unfilled, nothing in the Asia session
    outside JPY" is a search.
    """
    pos = {k: v for k, v in free.marginal.items() if v > 0}
    od = float(sum(pos.values()))
    funded = {k for k, v in book.items() if v > 1e-5}
    gap = max(target - sum(book.values()), 0.0)
    by_session: dict[str, float] = {}
    by_family: dict[str, float] = {}
    for name, mv in pos.items():
        parts = str(name).split("_")
        sess = parts[1] if len(parts) > 2 else (parts[0] if name.startswith("gold") else "?")
        by_session[sess] = by_session.get(sess, 0.0) + mv
        by_family[parts[0]] = by_family.get(parts[0], 0.0) + mv
    return {
        "opportunity_density": round(od, 6),
        "n_positive_marginal": len(pos),
        "n_funded": len(funded),
        "heat_gap": round(gap, 6),
        "positive_marginal_by_session": {k: round(v, 6) for k, v in
                                         sorted(by_session.items(), key=lambda kv: -kv[1])},
        "positive_marginal_by_family": {k: round(v, 6) for k, v in
                                        sorted(by_family.items(), key=lambda kv: -kv[1])[:15]},
        "research_request": ([] if gap <= 1e-6 else
                             [f"{gap:.2%} of the heat target is unfundable by the current "
                              f"library at its per-sleeve bounds"]),
    }


# ---------------------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------------------

def run(mode: str = "normal", *, seed: int = 0) -> dict[str, Any]:
    """One allocator pass. Returns the artifact it wrote."""
    t0 = time.time()
    heavy = mode == "heavy"
    daily, forward = build_evidence(force=heavy)
    live = live_days_by_sleeve()
    ev = sleeve_evidence(daily, forward, live)
    dd = worst_dd_r(daily)

    labels, probs = regime_state(daily) if mode in ("heavy", "normal") else ((), ())
    cfg = WorldConfig(seed=seed, regime_labels=labels, regime_probs=probs,
                      # The fast clock buys its speed here and nowhere else: a smaller world
                      # population, never a shortcut through the posterior or the crisis worlds.
                      n_worlds=256 if heavy else 128,
                      n_rows=384 if heavy else 256)

    cachef = CACHE / "worlds.npz"
    worlds: Worlds | None = None
    if mode == "fast" and cachef.exists() and time.time() - cachef.stat().st_mtime < 3600:
        try:
            z = np.load(cachef, allow_pickle=False)
            if tuple(z["names"]) == tuple(e.name for e in ev):
                worlds = Worlds(r=z["r"], names=tuple(str(x) for x in z["names"]),
                                crisis=z["crisis"], mu_draws=z["mu"],
                                note="reused cached world population")
                _log("world population reused from cache")
        except (OSError, ValueError, KeyError):
            worlds = None
    if worlds is None:
        worlds = sample_worlds(ev, cfg)
        _log(f"worlds {worlds.r.shape} crisis={int(worlds.crisis.sum())} {worlds.note}")
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cachef, r=worlds.r, names=np.array(worlds.names),
                                crisis=worlds.crisis, mu=worlds.mu_draws)
        except OSError as exc:
            _log(f"world cache not written ({exc}); next fast pass will resample")

    # 1. WHAT GROWTH ACTUALLY WANTS -- no mandate, no floor. This number certifies the target.
    bounds = per_sleeve_bounds(dd, HEAT_TARGET)
    free = optimise(ev, hard_cap=HEAT_HARD_CEILING, target=None, cfg=cfg, worlds=worlds,
                    max_per_sleeve=bounds)
    _log(f"free optimum H*={free.total_heat:.2%} ann={free.annual_growth_pct:.1f}% "
         f"P(annual loss)={free.prob_annual_loss:.1%}")

    # 2. THE CURVE, then the law.
    curve = growth_curve(ev, worlds, bounds, cfg) if heavy else {}
    if not curve and OUT.exists():
        try:                                    # a fast pass inherits the last heavy curve
            prev = json.loads(OUT.read_text("utf-8")).get("heat", {}).get("curve") or []
            curve = {float(h): float(g) for h, g in prev}
        except (OSError, ValueError, TypeError):
            curve = {}
    verdict = resolve(free.total_heat, curve=curve, target=HEAT_TARGET,
                      hard_ceiling=HEAT_HARD_CEILING, mandate=True,
                      allocator_ok=bool(free.heat) and math.isfinite(free.mean_log_growth))
    for why in verdict.reasons:
        _log(why)

    # 3. THE BOOK, at the heat the law resolved.
    if verdict.total_heat <= 0:
        book = AllocationResult(heat={}, total_heat=0.0, robust_score=0.0, mean_log_growth=0.0,
                                cvar_log_growth=0.0, annual_growth_pct=0.0, prob_annual_loss=0.0,
                                note="catastrophe guard: no heat")
    else:
        ub = {k: min(v, verdict.total_heat) for k, v in
              per_sleeve_bounds(dd, verdict.total_heat).items()}
        book = optimise(ev, hard_cap=HEAT_HARD_CEILING, target=verdict.total_heat, cfg=cfg,
                        worlds=worlds, max_per_sleeve=ub,
                        warm_start=current_book() or None)
    funded = {k: round(v, 6) for k, v in book.heat.items() if v > 1e-5}
    _log(f"book: {len(funded)} funded sleeves at {book.total_heat:.2%} total heat, "
         f"ann={book.annual_growth_pct:.1f}%")

    prev_book = current_book()
    nt = no_trade(prev_book, funded, book.mean_log_growth - free.mean_log_growth)
    opp = opportunity(free, funded, HEAT_TARGET)

    art: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "mode": mode,
        "elapsed_s": round(time.time() - t0, 1),
        "armed": ARMED.exists(),
        "advisory": not ARMED.exists(),
        "heat": {
            "total": round(verdict.total_heat, 6),
            "free_optimum": round(verdict.free_optimum, 6),
            "target": verdict.target, "hard_ceiling": verdict.hard_ceiling,
            "binding": verdict.binding, "certified": verdict.certified,
            "reasons": list(verdict.reasons),
            "curve": [[round(h, 4), round(g, 8)] for h, g in sorted(curve.items())],
        },
        "book": funded,
        "marginal_delta_elog": book.marginal,
        "growth": {
            "annual_growth_pct": book.annual_growth_pct,
            "mean_log_per_day": round(book.mean_log_growth, 8),
            "cvar_log_per_day": round(book.cvar_log_growth, 8),
            "prob_annual_loss": book.prob_annual_loss,
            "robust_score": round(book.robust_score, 8),
            "free_annual_growth_pct": free.annual_growth_pct,
        },
        "no_trade": nt,
        "opportunity": opp,
        "regime": {"probabilities": dict(probs), "conditioned": bool(labels)},
        "evidence": {
            "sleeves": len(ev), "rows": int(daily.shape[0]),
            "with_forward": sum(1 for e in ev if e.forward_days > 0),
            "with_live": sum(1 for e in ev if e.live_days > 0),
            "worlds": worlds.r.shape[0], "world_rows": worlds.r.shape[1],
            "note": worlds.note,
        },
        "solver": {"iterations": book.iterations, "converged": book.converged},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=2, default=str), encoding="utf-8")
    DONE.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")
    _log(f"-> {OUT.relative_to(ROOT)}  [{nt['verdict']}]  {art['elapsed_s']}s")
    return art


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("fast", "normal", "heavy"), default="normal")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    try:
        run(args.mode, seed=args.seed)
    except Exception as exc:
        # A crash here must never read as "no allocation was needed" (L1.28a). The artifact keeps
        # its last good content and the failure is loud and non-zero.
        _log(f"ALLOCATOR FAILED: {type(exc).__name__}: {exc}")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
