"""EX-ANTE INSTRUMENT VIABILITY, and the out-of-sample test it makes possible.

    "Calculate every sleeve we have currently, the most promising ones, all the most uncorrelated
     ones, as much quantity as you can find, and calculate the fastest book possible."
                                                            -- the principal, 2026-09-08

WHAT THIS EXISTS TO STOP. A mechanism certified on five symbols is five symbols of evidence, not
a mechanism, until it has been run somewhere nobody chose. Running it everywhere else is the
cheapest genuine out-of-sample this desk can buy -- it costs no waiting, unlike a forward clock --
and on 2026-09-08 it returned, for `session_range_breakout` on the `asia` window:

    in-sample (the 5 chosen symbols)      n=10,687   +0.1413R   t=+13.9   5/5 positive
    out-of-sample (26 other symbols)      n=52,562   -0.4046R   t=-49.6  13/26 positive

which reads as a dead mechanism and is not one. The pooled OOS number is dominated by instruments
whose ROUND TRIP EXCEEDS THEIR STOP DISTANCE -- ADAUSD at 1190% of the stop, BCHUSD at 206%,
BNBUSD at 204%. Those are not evidence about a breakout; they are evidence that you cannot pay a
spread wider than the thing you are betting on. Screened ex ante at cost/stop <= 15% the same
mechanism runs +0.0552R (t=+8.0, 9/11 OOS symbols positive), and the rank correlation between
cost/stop and expectancy across all 31 symbols is -0.855.

WHY THE SCREEN IS LEGITIMATE AND A P&L FILTER WOULD NOT BE. `cost_ratio` is built from the
measured spread and the ATR the family itself uses to place its stop. Both are known before a
single trade is taken, and neither touches the outcome. Dropping symbols because they LOST would
be a second pass of selection wearing a risk-management hat; dropping them because the desk
cannot pay their spread is arithmetic.

    cost_ratio = round-trip cost in price units / median stop distance

THE SCREEN IS NOT A PROMOTION. Clearing it means an instrument is capable of paying for the
trade, nothing more. A symbol still needs its own forward clock and the ten gates before it sees
capital -- this only decides what is worth enrolling.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

__all__ = [
    "DEFAULT_MAX_COST_RATIO",
    "MIN_TRADES",
    "cost_ratio",
    "effective_breadth",
    "screen",
]

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"

#: Where the screen sits by default. Measured 2026-09-08: at <=10% the OOS pool is +0.0540R over
#: 6 symbols, at <=15% it is +0.0552R over 11, and at <=25% it decays to +0.0332R over 19. The
#: bar is set at 15% because it is the loosest threshold that has not yet started paying for
#: instruments the desk cannot afford -- NOT because it maximised anything.
DEFAULT_MAX_COST_RATIO = 0.15

#: Fewer than this and a per-symbol expectancy is a rumour about the symbol.
MIN_TRADES = 100


def cost_ratio(round_trip_price: float, stop_distance: float) -> float:
    """Round-trip cost as a fraction of the stop the strategy actually places.

    Both arguments are in PRICE UNITS. `Costs.per_oz_roundtrip() / contract_oz` is the
    round trip in price units; the stop distance is whatever the family risks per trade.
    """
    if not (math.isfinite(round_trip_price) and math.isfinite(stop_distance)):
        return float("inf")
    if stop_distance <= 0:
        return float("inf")
    return float(round_trip_price) / float(stop_distance)


def effective_breadth(corr: np.ndarray) -> float:
    """k_eff = (sum of eigenvalues)^2 / sum of squares -- how many INDEPENDENT bets are here.

    Sixteen sleeves at a mean pairwise rho of 0.072 are worth 13.3 bets; the same mechanism on
    the five symbols it was fitted on is worth 4.1, and fifteen clocks on those five symbols are
    STILL worth 4.5 -- because `rr=1.5/2.0/2.5` on one symbol is one signal wearing three targets
    and correlates at 0.91-0.96. Counting parameterisations as breadth is how a book that looks
    diversified dies in one afternoon.
    """
    c = np.asarray(corr, dtype="float64")
    if c.ndim != 2 or c.shape[0] != c.shape[1] or c.shape[0] == 0:
        return float("nan")
    ev = np.clip(np.linalg.eigvalsh(0.5 * (c + c.T)), 0.0, None)
    denom = float((ev ** 2).sum())
    return float(ev.sum() ** 2 / denom) if denom > 0 else float("nan")


def screen(rows: Sequence[Mapping[str, Any]], *,
           max_cost_ratio: float = DEFAULT_MAX_COST_RATIO,
           min_trades: int = MIN_TRADES,
           in_sample: frozenset[str] | set[str] | None = None) -> dict[str, Any]:
    """Split a per-symbol replay into what the desk can pay for and what it cannot.

    Each row needs `symbol`, `n`, `exp`, `sd`, `cost` and `stop`. `in_sample` names the symbols
    the parameterisation was SELECTED on; their expectancy is reported separately and is never
    pooled into the out-of-sample verdict, because pooling it scores the selection twice.
    """
    sel = set(in_sample or ())
    kept: list[dict[str, Any]] = []
    priced_out: list[dict[str, Any]] = []
    thin: list[dict[str, Any]] = []
    for r in rows:
        n = int(r.get("n", 0) or 0)
        rec = dict(r)
        rec["cost_ratio"] = cost_ratio(float(r.get("cost", float("nan"))),
                                       float(r.get("stop", float("nan"))))
        rec["in_sample"] = str(r.get("symbol")) in sel
        if n < int(min_trades):
            rec["why"] = f"{n} trades against a {min_trades} floor"
            thin.append(rec)
        elif rec["cost_ratio"] > float(max_cost_ratio):
            rec["why"] = (f"round trip is {rec['cost_ratio']:.0%} of the stop distance; the "
                          "instrument cannot pay for the trade")
            priced_out.append(rec)
        else:
            kept.append(rec)

    def pool(rs: list[dict[str, Any]]) -> dict[str, Any]:
        rs = [r for r in rs if int(r.get("n", 0)) > 1]
        if not rs:
            return {"status": UNMEASURED, "symbols": 0, "n": 0,
                    "why": "no symbol cleared the screen with enough trades to pool"}
        n = sum(int(r["n"]) for r in rs)
        m = sum(float(r["exp"]) * int(r["n"]) for r in rs) / n
        dof = n - len(rs)
        if dof <= 0:
            return {"status": UNMEASURED, "symbols": len(rs), "n": n,
                    "why": "no residual degrees of freedom to pool a dispersion"}
        sd = math.sqrt(sum((float(r["sd"]) ** 2) * (int(r["n"]) - 1) for r in rs) / dof)
        se = sd / math.sqrt(n)
        return {"status": MEASURED, "symbols": len(rs), "n": n, "exp": m, "se": se,
                "t": (m / se if se > 0 else float("nan")),
                "ci95": (m - 1.96 * se, m + 1.96 * se),
                "positive": sum(float(r["exp"]) > 0 for r in rs)}

    oos = pool([r for r in kept if not r["in_sample"]])
    ins = pool([r for r in kept if r["in_sample"]])
    return {
        "kept": sorted(kept, key=lambda r: r["cost_ratio"]),
        "priced_out": sorted(priced_out, key=lambda r: r["cost_ratio"]),
        "thin": thin,
        "out_of_sample": oos, "in_sample": ins,
        "max_cost_ratio": float(max_cost_ratio),
        # THE OOS POOL IS THE ONE THAT DESCRIBES THE NEXT SYMBOL, and the next day. The in-sample
        # figure describes a window that has already been searched, so a book sized on it is
        # sized on its own selection.
        "why": (f"{len(kept)} symbol(s) can pay for the trade at cost/stop <= "
                f"{float(max_cost_ratio):.0%}; {len(priced_out)} priced out, {len(thin)} too "
                "thin to judge"
                + (f"; out-of-sample {oos['exp']:+.4f}R (t={oos['t']:+.2f}, "
                   f"{oos['positive']}/{oos['symbols']} positive)"
                   if oos["status"] == MEASURED else f"; out-of-sample {oos['why']}")),
    }
