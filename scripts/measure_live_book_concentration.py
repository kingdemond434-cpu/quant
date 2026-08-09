#!/usr/bin/env python3
"""WHAT IS THE LIVE BOOK'S ACTUAL CONCENTRATION -- measured on real bars, not on the weight cap.

THE BOOK. data/cashcarry_config.json carries ``"top": 4``. The live cash-carry executor does not
import PortfolioConstraints at all; it controls concentration by COUNT, so four names is 25% each
BY CONSTRUCTION. The desk's nominal single-name cap is 0.25 and BRAIN's is 0.08.

THE THREE NUMBERS THIS SCRIPT PRODUCES, AND WHY ONLY THE THIRD IS A MEASUREMENT.

  1. NOMINAL. max weight 1/top against the cap. At top=4 the equal-weight book sits EXACTLY on
     0.25, so the cap cannot bind in either direction: it is 1/n, not a choice, and no tighter cap
     has a feasible solution (0.08 needs >= 13 names). Reporting "cap satisfied" here is content-
     free, which is precisely the failure this script exists to expose.
  2. CORRELATION-BLIND. 1 / sum(w^2) = 4.00 effective positions, the number
     libs/portfolio/diversification.effective_bets reports today. It is the C = I special case of
     the truth and it is wrong by a factor this script measures.
  3. CORRELATION-ADJUSTED. 1 / (w' C w) with C estimated from real OKX daily closes. This is the
     quantity a concentration limit was always reaching for.

WHICH FOUR NAMES -- AND WHY THE ANSWER IS AN ENUMERATION RATHER THAN A GUESS. The executor ranks
by net funding and the ranking rotates, and neither data/cashcarry_positions.json nor
data/cashcarry_trades.json exists in this tree, so THE IDENTITY OF THE FOUR HELD NAMES IS NOT ON
DISK. Picking four plausible tickers would describe the picker, not the desk. Instead every
C(N, top) equal-weight subset of the measured panel is evaluated, and the artifact reports the
full distribution: the best four names the universe can offer, the worst, and the median. That is
strictly more informative than one draw, and it is the only honest answer to a question whose
input is missing -- the verdict has to hold for whichever four the funding rank picks today.

NO MARKET DATA IS EVER FABRICATED HERE. Absent panel -> BLOCKED report naming the missing input,
non-zero exit, and no fallback to simulation.

    python3 scripts/measure_live_book_concentration.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

from measure_cross_section_breadth import (  # noqa: E402
    live_columns,
    load_cache,
    log_returns,
    residualise_trailing,
)

from libs.portfolio.concentration import (  # noqa: E402
    BRAIN_MAX_WEIGHT,
    LIVE_BOOK_MEAN_CORR,
    MIN_EFFECTIVE_POSITIONS,
    concentration_verdict,
    effective_positions,
    max_weight_for,
)
from libs.portfolio.models import PortfolioConstraints  # noqa: E402
from libs.research.cohort_independence import demeaning_floor  # noqa: E402
from libs.research.cohort_independence import effective_bets as equicorrelation_bets  # noqa: E402

_CONFIG = _ROOT / "data" / "cashcarry_config.json"
_POSITIONS = _ROOT / "data" / "cashcarry_positions.json"
_OUT = _ROOT / "reports" / "live_book_concentration.json"

#: Enumerating every k-subset is exact and cheap at the desk's width (C(28,4) = 20,475), but it is
#: combinatorial and would silently become a hang on a wider universe. Above this the script
#: samples instead and SAYS SO in the artifact rather than quietly changing method.
_MAX_ENUMERATED_SUBSETS = 500_000
_SUBSET_SAMPLE = 100_000


def _equal_weight_neff(corr: np.ndarray, idx: tuple[int, ...]) -> float:
    """1 / (w' C w) for an equal-weight book on `idx`. Exact, and the closed form is the point.

    At equal weights w' C w is just the MEAN of the k x k submatrix, so the whole enumeration is
    submatrix means rather than 20,475 quadratic forms. `effective_positions` is the authority and
    is used for the reported books; this is its arithmetic identity, asserted by the tests.
    """
    sub = corr[np.ix_(idx, idx)]
    quad = float(sub.mean())
    if quad <= 0.0:
        return float("nan")
    return min(float(len(idx)), max(1.0, 1.0 / quad))


def _pairwise(corr: np.ndarray) -> np.ndarray:
    iu = np.triu_indices(corr.shape[0], k=1)
    return np.asarray(corr[iu], dtype="float64")


def _distribution(corr: np.ndarray, symbols: tuple[str, ...], k: int,
                  rng: np.random.Generator) -> dict[str, Any]:
    """Effective positions over every (or a sample of) equal-weight k-subset of the panel."""
    n = corr.shape[0]
    if k < 1 or k > n:
        return {"blocked": f"cannot form a {k}-name book from {n} measured symbols"}
    total = 1
    for i in range(k):
        total = total * (n - i) // (i + 1)
    exhaustive = total <= _MAX_ENUMERATED_SUBSETS
    if exhaustive:
        subsets = list(combinations(range(n), k))
    else:
        seen: set[tuple[int, ...]] = set()
        while len(seen) < _SUBSET_SAMPLE:
            seen.add(tuple(sorted(rng.choice(n, size=k, replace=False).tolist())))
        subsets = sorted(seen)
    vals = np.array([_equal_weight_neff(corr, s) for s in subsets], dtype="float64")
    good = np.isfinite(vals)
    vals, subsets = vals[good], [s for s, g in zip(subsets, good, strict=True) if g]
    i_min, i_max = int(np.argmin(vals)), int(np.argmax(vals))
    return {
        "n_subsets": len(subsets),
        "exhaustive": exhaustive,
        "min": float(vals[i_min]),
        "min_book": [symbols[i] for i in subsets[i_min]],
        "p25": float(np.quantile(vals, 0.25)),
        "median": float(np.median(vals)),
        "mean": float(vals.mean()),
        "p75": float(np.quantile(vals, 0.75)),
        "max": float(vals[i_max]),
        "max_book": [symbols[i] for i in subsets[i_max]],
        "share_clearing_min_effective_positions": float(
            np.mean(vals >= MIN_EFFECTIVE_POSITIONS)),
    }


def _blocked(missing: str, remedy: str) -> dict[str, Any]:
    return {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "BLOCKED",
        "missing_input": missing,
        "remedy": remedy,
        "consequence": "the live book's correlation-adjusted concentration is UNMEASURED. An "
                       "unknown correlation is not a diversified book; UNMEASURED IS NOT PASSED.",
    }


def build_report(*, seed: int = 20260801) -> tuple[dict[str, Any], int]:
    panel = load_cache()
    if panel is None:
        return _blocked(
            "data/perp_close_panel.json (aligned daily close panel)",
            "python3 scripts/measure_cross_section_breadth.py --fetch"), 1

    top = 4
    cfg_read = False
    try:
        cfg = json.loads(_CONFIG.read_text("utf-8"))
        top = int(cfg.get("top", 4))
        cfg_read = True
    except (OSError, ValueError, TypeError):
        cfg_read = False

    rets = log_returns(panel.closes)
    keep = live_columns(rets)
    rets = rets[:, keep]
    symbols = tuple(s for s, k in zip(panel.symbols, keep, strict=True) if bool(k))
    n_obs, n = rets.shape
    corr = np.corrcoef(rets, rowvar=False)
    pair = _pairwise(corr)
    mean_corr, median_corr = float(pair.mean()), float(np.median(pair))

    rng = np.random.default_rng(seed)
    dist = _distribution(corr, symbols, top, rng)

    # THE HEDGED COUNTERFACTUAL, on trailing betas only. `residualise_trailing` fits row t's beta
    # on rows [0, t) so truncating the sample cannot move any earlier residual -- prefix
    # invariance, which is what makes this a book a live desk could actually have held rather than
    # an in-sample upper bound.
    resid = residualise_trailing(rets)
    live_rows = np.isfinite(resid).all(axis=1)
    resid = resid[live_rows]
    hedged: dict[str, Any]
    if resid.shape[0] > resid.shape[1] and resid.shape[1] >= top:
        rcorr = np.corrcoef(resid, rowvar=False)
        rpair = _pairwise(rcorr)
        hedged = {
            "n_obs": int(resid.shape[0]),
            "mean_corr": float(rpair.mean()),
            "demeaning_floor": demeaning_floor(n),
            "excess_above_floor": float(rpair.mean()) - demeaning_floor(n),
            "distribution": _distribution(rcorr, symbols, top, rng),
            "caveat": "cross-sectional factor removal forces mean pairwise residual correlation "
                      "toward -1/(N-1) by arithmetic alone, so this is an UPPER BOUND on what "
                      "hedging buys, not a promise (cohort_independence.demeaning_floor).",
        }
    else:
        hedged = {"blocked": "too few trailing-residual rows to estimate a correlation matrix"}

    # The reported book: equal weights on the MEDIAN subset is not a real book either, so the
    # verdict is run on the two ends of the real distribution plus the equicorrelation stand-in.
    w = np.full(top, 1.0 / top)
    eq = np.full((top, top), mean_corr)
    np.fill_diagonal(eq, 1.0)
    v_eq = concentration_verdict(w, eq)
    idx_worst = tuple(symbols.index(s) for s in dist["min_book"]) if "min_book" in dist else ()
    idx_best = tuple(symbols.index(s) for s in dist["max_book"]) if "max_book" in dist else ()
    v_worst = concentration_verdict(w, corr[np.ix_(idx_worst, idx_worst)]) if idx_worst else None
    v_best = concentration_verdict(w, corr[np.ix_(idx_best, idx_best)]) if idx_best else None

    nominal_cap = float(PortfolioConstraints().max_weight)
    max_w = 1.0 / top
    rep: dict[str, Any] = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "MEASURED",
        "panel": {
            "source": panel.source,
            "fetched_utc": panel.fetched_utc,
            "n_symbols": n,
            "n_obs": int(n_obs),
            "symbols": list(symbols),
            "dropped_short_history": list(panel.dropped_short),
        },
        "live_book": {
            "positions": top,
            "config": str(_CONFIG.relative_to(_ROOT)),
            "config_read": cfg_read,
            "held_names": None,
            "held_names_status": (
                f"UNMEASURED -- {_POSITIONS.name} does not exist in this tree, so which four "
                "names the funding rank currently holds is not on disk. Every 4-subset of the "
                "measured panel is enumerated instead; the verdict must hold for all of them."),
            "equal_weight_by_construction": True,
        },
        "nominal_cap": {
            "desk_max_weight": nominal_cap,
            "brain_max_weight": BRAIN_MAX_WEIGHT,
            "breadth_aware_cap_at_n": max_weight_for(top),
            "actual_max_weight": max_w,
            "binds": bool(max_w > nominal_cap + 1e-12),
            "slack": nominal_cap - max_w,
            "names_required_for_brain_cap": int(np.ceil(1.0 / BRAIN_MAX_WEIGHT)),
            "reading": (
                f"at top={top} the equal-weight max weight is exactly 1/{top} = {max_w:.3f}, so "
                f"the {nominal_cap:.2f} cap is satisfied with {nominal_cap - max_w:.3f} slack and "
                f"CANNOT BIND. No tighter cap is satisfiable at this width; BRAIN's "
                f"{BRAIN_MAX_WEIGHT:.2f} needs >= {int(np.ceil(1.0 / BRAIN_MAX_WEIGHT))} names "
                "and has an empty feasible set here."),
        },
        "correlation": {
            "measured_mean_pairwise": mean_corr,
            "measured_median_pairwise": median_corr,
            "recorded_constant_LIVE_BOOK_MEAN_CORR": LIVE_BOOK_MEAN_CORR,
            "universe_n_eff_equicorrelation": equicorrelation_bets(n, mean_corr),
            "equicorrelation_ceiling_1_over_rho": (1.0 / mean_corr) if mean_corr > 0 else None,
        },
        "effective_positions": {
            "correlation_blind_1_over_sum_w2": float(1.0 / float(np.sum(w**2))),
            "at_measured_equicorrelation": float(effective_positions(w, eq)),
            "at_recorded_constant_0.638": equicorrelation_bets(top, LIVE_BOOK_MEAN_CORR),
            "distribution_over_all_4_name_books": dist,
            "overstatement_x_of_correlation_blind": (
                float(1.0 / float(np.sum(w**2))) / float(effective_positions(w, eq))),
            "min_effective_positions_floor": MIN_EFFECTIVE_POSITIONS,
        },
        "verdicts": {
            "equicorrelation_stand_in": v_eq.summary(),
            "worst_real_4_name_book": v_worst.summary() if v_worst else None,
            "best_real_4_name_book": v_best.summary() if v_best else None,
            "any_4_name_book_clears_floor": bool(
                dist.get("max", float("nan")) >= MIN_EFFECTIVE_POSITIONS),
        },
        "hedged_counterfactual": hedged,
    }
    return rep, 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)
    rep, code = build_report()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if rep["status"] == "BLOCKED":
        print(f"BLOCKED: {rep['missing_input']}")
    else:
        print(rep["nominal_cap"]["reading"])
        for k, v in rep["verdicts"].items():
            print(f"{k}: {v}")
    print(f"wrote {out}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
