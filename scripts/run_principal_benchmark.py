#!/usr/bin/env python3
"""PRINCIPAL BENCHMARK (R0213) -- does the machine actually beat the human it was built to copy?

PRINCIPAL ORDER (2026-07-31): *"surpass my profit potential of ss and use Claude intelligence to
surpass me in compounding like human trader."*

WHY THIS IS A FENCE AND NOT A PEP TALK. "Surpass me" is only a real instruction if something
MEASURES it, and nothing did. The desk already benchmarks every sleeve against unlevered
buy-and-hold, because a levered sleeve that merely tracks the index is taking risk for nothing
(L1.6). The same logic applies one level up: a discretionary machine that merely matches the
human's own method is engineering for nothing. So the human's method becomes the second
benchmark, computed exactly like the first.

THE COUNTERFACTUAL, and its one honest limit. The principal's demonstrated method is a 10% risk
fraction per trade behind a structural stop that gets trailed (0.1 lots on a 1k account, stop
moved up to bank profit while letting it run). That is re-priced onto THE DESK'S OWN CLOSED
TRADES: same calls, same entries, same stops, same exits -- only the risk fraction changes. Every
other variable is held fixed, so the difference is attributable to sizing policy alone.

WHAT THIS THEREFORE DOES *NOT* PROVE, stated plainly because the comparison is seductive: it does
NOT show the machine beats the principal. It shows whether the machine's SIZING beats his sizing
ON THE MACHINE'S OWN CALLS. His selection is unmeasured -- the desk has seen one of his trades --
so a verdict here is about risk policy, never about who picks better. Claiming otherwise would be
the exact self-flattery the paper-book resolver exists to prevent.

THE ARITHMETIC IS EXACT, not simulated. Cost in R is size-independent -- (cost/notional) divided
by (stop/price), leverage cancels -- so the whole outcome scales linearly with the risk fraction:
    net_R              = equity_return / risk_fraction        (what one R actually paid, net)
    equity_return(f)   = net_R * f                            (the same trade at any size)
    g(f)               = mean( ln(1 + net_R * f) )            (what compounds)
No re-walking, no second set of assumptions.

AND THE RESULT IS NOT A FOREGONE CONCLUSION, which is what makes it worth computing. At a
measured hit rate above ~38% his 10% wins and the desk's cap is costing growth; below it, his
sizing is past full Kelly on net odds and loses while the same trades at 6% make money. The
crossover is real and nobody yet knows which side the sleeve is on.

    python scripts/run_principal_benchmark.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_STATE = "data/principal_benchmark.json"

#: THE PRINCIPAL'S DEMONSTRATED RISK FRACTION. 0.10 = 0.1 lots on a 1,000 account, stated by him
#: directly ("10 percent risk, 10 dollar per one dollar gold move") and corrected once when this
#: desk first inferred it wrong from a screenshot. It is a MEASURED parameter of his method, not
#: an estimate -- which is exactly why it is the half of his method that can be benchmarked.
PRINCIPAL_RISK = 0.10

#: Minimum closed trades before a verdict. 20 because the standard error on a per-trade growth
#: difference is still wide there but the SIGN is usually stable -- and the sign is the whole
#: question. Below it the comparison reports UNMEASURED, never a lead.
MIN_FOR_VERDICT = 20


def _marks(root: Path) -> list[dict[str, Any]]:
    try:
        pnl = json.loads((root / "data/paper_book_pnl.json").read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return [m for m in (pnl.get("marks") or [])
            if m.get("closed") and m.get("equity_return") is not None
            and float((m.get("sizing") or {}).get("risk_fraction") or 0.0) > 0.0]


def net_r_per_trade(marks: list[dict[str, Any]]) -> list[float]:
    """What one R actually paid, NET of costs, per closed trade -- the size-independent unit.

    Recovered from the mark rather than re-derived: equity_return already has real fees,
    slippage and funding deducted, and dividing by the risk fraction that produced it removes
    size. That is what makes re-pricing at any other size exact instead of a second model."""
    out = []
    for m in marks:
        f = float((m.get("sizing") or {}).get("risk_fraction") or 0.0)
        if f > 0:
            out.append(float(m["equity_return"]) / f)
    return out


def growth_at(net_rs: list[float], f: float) -> dict[str, Any]:
    """E[log] per trade and the compounded curve at risk fraction f."""
    if not net_rs:
        return {"state": "UNMEASURED", "n": 0}
    ruin = [r for r in net_rs if 1.0 + r * f <= 0.0]
    if ruin:
        # A single trade that takes the account to zero ends the sequence -- log is undefined and
        # the honest report is RUIN, never a number produced by skipping the trade that killed it.
        return {"state": "RUIN", "n": len(net_rs), "risk_fraction": f,
                "n_ruinous": len(ruin),
                "why": f"{len(ruin)} trade(s) at {f:.0%} risk would have taken the account to "
                       "zero or below. There is no growth rate past that point, and dropping the "
                       "trade that ended the sequence is how a backtest hides a blow-up."}
    g = sum(math.log(1.0 + r * f) for r in net_rs) / len(net_rs)
    return {"state": "MEASURED", "n": len(net_rs), "risk_fraction": f,
            "g_per_trade": round(g, 6),
            "equity_multiple": round(math.exp(g * len(net_rs)), 4),
            "worst_trade": round(min(net_rs) * f, 4)}


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    marks = _marks(root)
    net_rs = net_r_per_trade(marks)
    desk_f = (sorted(float((m.get("sizing") or {}).get("risk_fraction") or 0.0)
                     for m in marks)[len(marks) // 2] if marks else 0.06)
    desk = growth_at(net_rs, desk_f)
    principal = growth_at(net_rs, PRINCIPAL_RISK)

    if len(net_rs) < MIN_FOR_VERDICT:
        verdict = {
            "state": "UNMEASURED", "n": len(net_rs), "need": MIN_FOR_VERDICT,
            "why": f"{len(net_rs)}/{MIN_FOR_VERDICT} closed trades -- no verdict is available, "
                   "and a partial record must not read as a lead. The principal's own record is "
                   "ONE trade, so an early claim here would be two small samples flattering each "
                   "other."}
    elif desk.get("state") == "RUIN" or principal.get("state") == "RUIN":
        loser = "the principal's 10%" if principal.get("state") == "RUIN" else "the desk's cap"
        verdict = {"state": "AHEAD" if principal.get("state") == "RUIN" else "BEHIND",
                   "why": f"{loser} sizing hit RUIN on this record -- survival decides before "
                          "growth does, and a sequence that ends has no rate to compare."}
    else:
        d, p = float(desk["g_per_trade"]), float(principal["g_per_trade"])
        verdict = {
            "state": "AHEAD" if d > p else ("BEHIND" if d < p else "LEVEL"),
            "desk_g": d, "principal_g": p, "edge_per_trade": round(d - p, 6),
            "why": (f"the desk's {desk_f:.0%} sizing compounds at {d:+.5f}/trade against "
                    f"{p:+.5f} for the principal's {PRINCIPAL_RISK:.0%} on the SAME trades. "
                    + ("The cap is earning its keep: his fraction is past full Kelly on these "
                       "net odds, where extra size buys variance and loses growth."
                       if d > p else
                       "His fraction is doing better here, which means the desk's cap is costing "
                       "growth on a hit rate this good -- the cap should rise as the measured "
                       "rate justifies it (that is what measured_risk_cap already does)."))}

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.6 -- a sleeve is benchmarked against what it claims to beat. Buy-and-hold is "
               "the first benchmark; the human method this sleeve was built to copy is the "
               "second, and neither is optional.",
        "status": verdict["state"],
        "n_closed": len(net_rs),
        "desk": desk, "principal": principal,
        "verdict": verdict,
        "scope_limit": "this compares SIZING POLICY on the desk's own calls, holding entries, "
                       "stops and exits fixed. It does NOT show the machine beats the principal: "
                       "his SELECTION is unmeasured (the desk has seen one of his trades), so a "
                       "verdict here is about risk policy, never about who picks better.",
        "where_the_machine_should_win": [
            "INDEPENDENT BETS -- 18 instruments watched continuously across every session. A "
            "human sleeps, and g_year scales linearly in the number of independent bets. This is "
            "the term the machine can win outright and the one it is currently wasting, since "
            "correlated crypto perps held at once are close to one bet.",
            "CONSISTENCY -- no tilt, no revenge trade, no fatigue. The human's visible record is "
            "his best trade; the machine's record is every trade, which is a harder bar honestly "
            "measured.",
            "MEASUREMENT -- the trail width, the risk cap and the payoff shape are swept against "
            "the desk's own marks. A human cannot A/B his own trail across 200 trades.",
        ],
        "where_the_human_still_wins": [
            "SELECTION -- he took one setup he had conviction in; the sleeve takes every 2-of-3 "
            "consensus. Conviction on few setups can carry a far higher hit rate.",
            "WINNER SHAPE -- his one visible trade ran ~6R against the ladder's assumed 3R, and "
            "the winner shape is the steepest term in the growth identity.",
        ],
        "detail": (f"{verdict['state']}: {verdict['why'][:150]}"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT)
    out = _ROOT / _STATE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"principal benchmark (L1.6): {rep['detail'][:170]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
