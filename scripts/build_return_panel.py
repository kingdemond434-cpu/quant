"""THE MISSING PRIMITIVE: row-aligned realised return series, one column per symbol.

WHY THIS EXISTS. Two gates were built and neither could be wired, for the same reason: nothing on
this desk produces per-signal return series on a common timestamp grid.
libs/research/marginal_admission.py needs a candidate series and an incumbent matrix;
libs/risk/sleeve_allocation.py needs a correlation between sleeves. Both were reduced to unwired
code by one absent artifact. This is that artifact, built from the desk's OWN realised fills rather
than from a backtest -- L1.4, reality outranks simulation.

CONSTRUCTION. Every closed trade contributes net/notional as its return. Trades are bucketed by
CLOSE DATE and aggregated within a symbol-day as sum(net)/sum(notional), i.e. notional-weighted,
so two small trades cannot outvote one large one. The grid spans every date in the file, so all
columns share a ruler -- the same-ruler law is the whole point of a panel, and a correlation
computed across misaligned rows is a number that means nothing.

THE ZERO-FILL DECISION, and it is a real methodological choice rather than a default. A day on
which a symbol had no closing trade is recorded as 0.0, because a strategy that is flat genuinely
earned zero that day -- that IS its return series. But co-occurring zeros across two mostly-flat
strategies create correlation that reflects shared INACTIVITY rather than shared exposure. So this
reports correlation BOTH ways: zero-filled (the strategy's true return stream) and restricted to
days where both symbols actually traded (the exposure relationship). Where the two disagree, the
disagreement is the finding, not an inconvenience -- the same stance cohort_independence.py takes
toward its two effective-N estimators.

WHAT IT REFUSES TO DO. It does not lower MIN_OVERLAP to manufacture a verdict. With 500 trades
spread across dozens of symbols, most pairs will not have enough common days, and the honest output
is "not measurable" for those. A panel that reports confident correlations from six overlapping
days would be worse than no panel, because it would be believed.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research import marginal_admission as ma  # noqa: E402
from libs.research.cohort_independence import effective_bets  # noqa: E402

_TRADES = _ROOT / "data/cashcarry_trades.json"
_OUT = _ROOT / "data/return_panel.json"

#: A symbol needs at least this many ACTIVE days before it is treated as a column worth gating on.
#: Below it the series is mostly zero-fill and its correlation describes inactivity, not strategy.
MIN_ACTIVE_DAYS = 5


def _closed_rows() -> list[dict[str, Any]]:
    rows = json.loads(_TRADES.read_text("utf-8"))
    out = []
    for r in rows:
        if not isinstance(r, dict) or r.get("event") != "close":
            continue
        if not r.get("closed") or r.get("symbol") is None:
            continue
        try:
            notional = float(r.get("notional") or 0.0)
            net = float(r.get("net"))
        except (TypeError, ValueError):
            continue
        if notional <= 0 or not np.isfinite(net):
            continue
        out.append({"symbol": str(r["symbol"]), "net": net, "notional": notional,
                    "date": str(r["closed"])[:10]})
    return out


def build_panel() -> tuple[list[str], list[str], np.ndarray, dict[str, int]]:
    """Return (dates, symbols, matrix[T,k] zero-filled, active_days_per_symbol)."""
    rows = _closed_rows()
    if not rows:
        return [], [], np.empty((0, 0)), {}

    agg_net: dict[tuple[str, str], float] = defaultdict(float)
    agg_not: dict[tuple[str, str], float] = defaultdict(float)
    for r in rows:
        k = (r["date"], r["symbol"])
        agg_net[k] += r["net"]
        agg_not[k] += r["notional"]

    dates = sorted({d for d, _ in agg_net})
    active = defaultdict(int)
    for _, sym in agg_net:
        active[sym] += 1
    symbols = sorted(s for s, n in active.items() if n >= MIN_ACTIVE_DAYS)

    di = {d: i for i, d in enumerate(dates)}
    si = {s: j for j, s in enumerate(symbols)}
    mat = np.zeros((len(dates), len(symbols)), dtype=float)
    for (d, s), net in agg_net.items():
        if s in si:
            mat[di[d], si[s]] = net / agg_not[(d, s)]
    return dates, symbols, mat, dict(active)


def _pairwise(mat: np.ndarray, symbols: list[str]) -> dict[str, Any]:
    """Correlation two ways: zero-filled, and restricted to jointly-active days."""
    k = len(symbols)
    filled, joint = [], []
    for a in range(k):
        for b in range(a + 1, k):
            x, y = mat[:, a], mat[:, b]
            if x.std() > 0 and y.std() > 0:
                filled.append(float(np.corrcoef(x, y)[0, 1]))
            both = (x != 0) & (y != 0)
            n = int(both.sum())
            if n >= 3 and x[both].std() > 0 and y[both].std() > 0:
                joint.append((float(np.corrcoef(x[both], y[both])[0, 1]), n))
    mean_filled = float(np.mean(filled)) if filled else float("nan")
    mean_joint = float(np.mean([c for c, _ in joint])) if joint else float("nan")
    overlaps = sorted(n for _, n in joint)
    return {"mean_pairwise_zero_filled": mean_filled,
            "mean_pairwise_jointly_active": mean_joint,
            "n_pairs_zero_filled": len(filled), "n_pairs_jointly_active": len(joint),
            "max_joint_overlap_days": max(overlaps, default=0),
            # The MEDIAN, not the max, is what the confidence bound is taken at: the max is the
            # single best-observed pair and using it would price every other pair's correlation as
            # if it were the most-observed one.
            "median_joint_overlap_days": int(np.median(overlaps)) if overlaps else 0}


def _independence(k: int, pw: dict[str, Any]) -> tuple[float, float, float, str]:
    """Effective bets, published from the CONSERVATIVE correlation -- never the flattering one.

    THE DEFECT THIS FIXES. This script computed correlation two ways, printed both, stored both,
    and then fed the headline `effective_bets` from the ZERO-FILLED one, which is the more
    forgiving of the two numbers it had just computed itself. Measured 2026-08-12 on the live
    panel: rho 0.198 zero-filled vs 0.421 jointly-active over 8 columns, publishing 3.36
    effective bets where the jointly-active reading gives 2.03 -- a 66% overstatement of
    diversification. Reading the more forgiving of two disagreeing counters is a defect class
    this desk has paid for before.

    WHY THE CONSERVATIVE DIRECTION IS NOT MERELY TASTE. Over-estimating independence is the
    dangerous direction under every sizing rule the desk owns: a Kelly bettor who believes it
    holds 3.4 independent bets when it holds 2.0 over-levers, and Kelly's penalty is asymmetric.
    Under-estimating costs a little size that later evidence reclaims. Same asymmetry, same
    reasoning, and the same instrument as marginal_admission._fisher_upper, which already treats
    a correlation the desk cannot pin down as duplicate-like rather than as independence.

    ZERO-FILL IS NOT WRONG, IT ANSWERS A DIFFERENT QUESTION. On a day a sleeve chose not to trade
    its return really is zero, so the zero-filled series is the true P&L stream. But two sleeves
    that are rarely active on the same day look uncorrelated for a reason that is an accident of
    scheduling, not a property of their mechanisms -- and the book getting fuller is the plan.
    Both numbers are published; only the conservative one is headlined.

    UNMEASURABLE READS AS ONE BET, NEVER AS MANY (L1.28a). With no jointly-active pairs there is
    no evidence these columns are distinct, and 'we cannot tell' must not render as health.
    """
    rho_zf = pw["mean_pairwise_zero_filled"]
    rho_ja = pw["mean_pairwise_jointly_active"]
    n_eff_zf = effective_bets(k, rho_zf) if np.isfinite(rho_zf) else float("nan")
    n_eff_ja = effective_bets(k, rho_ja) if np.isfinite(rho_ja) else float("nan")
    if not np.isfinite(rho_ja):
        return 1.0, n_eff_zf, n_eff_ja, ("UNMEASURED -- no jointly-active pair, so a duplicate "
                                         "cannot be ruled out; floored at one bet")
    n_overlap = int(pw.get("median_joint_overlap_days", 0) or 0)
    rho_bound = ma._fisher_upper(float(rho_ja), n_overlap)
    n_eff = effective_bets(k, rho_bound)
    return n_eff, n_eff_zf, n_eff_ja, (
        f"jointly-active rho {rho_ja:+.3f} at median overlap {n_overlap}d -> Fisher upper bound "
        f"{rho_bound:.3f} (zero-filled would have published {n_eff_zf:.2f})")


def main() -> int:
    dates, symbols, mat, active = build_panel()
    if not symbols:
        print("no symbol has enough active days to form a column -- panel not built")
        return 1

    ann = 365.0
    sharpes = {s: ma._sharpe(mat[:, j], ann) for j, s in enumerate(symbols)}
    pw = _pairwise(mat, symbols)
    n_eff, n_eff_zf, n_eff_ja, basis = _independence(len(symbols), pw)

    print(f"RETURN PANEL: {len(dates)} days x {len(symbols)} symbols "
          f"({dates[0]} .. {dates[-1]})")
    print(f"  mean pairwise rho  zero-filled: {pw['mean_pairwise_zero_filled']:+.3f} "
          f"({pw['n_pairs_zero_filled']} pairs)")
    print(f"  mean pairwise rho  jointly-active: {pw['mean_pairwise_jointly_active']:+.3f} "
          f"({pw['n_pairs_jointly_active']} pairs, max overlap "
          f"{pw['max_joint_overlap_days']}d)")
    print(f"  effective bets from {len(symbols)} columns: {n_eff:.2f}  [{basis}]")
    print(f"    zero-filled {n_eff_zf:.2f} vs jointly-active {n_eff_ja:.2f} -- the published "
          "number is the LOWER, never the flattering one")
    print("\n  top columns by realised Sharpe (net of fees, own fills):")
    for s in sorted(symbols, key=lambda x: -sharpes[x])[:8]:
        print(f"    {s:14s} Sharpe {sharpes[s]:+7.3f}   active {active[s]:3d}d")

    # THE ADMISSION AUDIT. Rank by realised Sharpe, seed the book with the best column, then ask of
    # each remaining column the question the desk has never asked: does it add anything the book
    # does not already own? This is the first time the gate runs on real realised returns.
    order = sorted(symbols, key=lambda x: -sharpes[x])
    kept = [order[0]]
    verdicts = []
    for cand in order[1:]:
        inc = np.column_stack([mat[:, symbols.index(s)] for s in kept])
        v = ma.evaluate(mat[:, symbols.index(cand)], inc, periods_per_year=ann)
        verdicts.append({"symbol": cand, **v.to_dict()})
        if v.admitted:
            kept.append(cand)

    print(f"\n  MARGINAL-CONTRIBUTION AUDIT (seed {order[0]}):")
    print(f"    admitted {len(kept)} of {len(symbols)} columns -> {kept}")
    for v in verdicts[:10]:
        print(f"    {v['symbol']:14s} {'ADMIT' if v['admitted'] else 'reject':6s}  {v['reason'][:88]}")

    _OUT.write_text(json.dumps({
        "generated": datetime.now(tz=UTC).isoformat(),
        "dates": dates, "symbols": symbols,
        "returns": mat.tolist(),
        "active_days": {s: active[s] for s in symbols},
        "sharpes": sharpes, "correlation": pw, "effective_bets": n_eff,
        "effective_bets_basis": basis,
        "effective_bets_zero_filled": n_eff_zf,
        "effective_bets_jointly_active": n_eff_ja,
        "admission_audit": {"seed": order[0], "kept": kept, "verdicts": verdicts},
        "note": "Returns are net/notional per closed trade, notional-weighted within a symbol-day, "
                "zero-filled on inactive days. Zero-fill is the strategy's true return stream, but "
                "when activity barely overlaps it DEFLATES measured correlation -- one column's "
                "moves land against the other's zeros -- so mostly-flat strategies read as "
                "diversified when they are merely out of phase. Measured 2026-08-12: rho +0.198 "
                "zero-filled vs +0.421 jointly-active on the same 8 columns. Both are published; "
                "effective_bets is headlined from the CONSERVATIVE one via a Fisher upper bound, "
                "because over-estimating independence over-levers and under-estimating it costs "
                "size that later evidence reclaims.",
    }, indent=2), "utf-8")
    print(f"\n-> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
