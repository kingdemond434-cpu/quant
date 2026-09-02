#!/usr/bin/env python3
"""WHICH BOOK GROWS FASTEST -- current sleeves, replacements, or the union.

THE QUESTION THIS ANSWERS. `allocation.py` optimises weights for ONE fixed set of sleeves. It
never asks whether a DIFFERENT set would grow faster, so a genuinely better, less correlated
edge could sit in the certified pile forever while a worse one holds capital. This ranks whole
BOOK COMPOSITIONS by expected log growth, which is the quantity the desk actually maximises:

    current            the sleeves holding capital today
    +candidate         current plus each certified candidate, one at a time
    -worst +candidate  the swap: drop the weakest current sleeve, add the candidate
    union              everything at once

and reports annualised growth for each, so "add", "swap" and "leave it alone" are compared on
one number instead of argued about.

WHY GROWTH AND NOT SHARPE. A sleeve with a lower Sharpe that is uncorrelated to the book can
raise geometric growth more than a higher-Sharpe near-duplicate, because growth is compounded
and correlation shows up in the variance drag. Ranking by Sharpe systematically prefers the
duplicate. That is the whole reason this file computes E[log W] per composition rather than
sorting a column.

IT SCORES THROUGH `libs.portfolio.robust_elog`, NOT THROUGH ITS OWN ARITHMETIC. The first
version equally weighted each composition, on the reasoning that optimising weights inside a
composition would let the optimiser paper over a bad member by giving it ~0 weight. That
reasoning was wrong in a way the first real run made obvious: equal weighting means adding an
Nth sleeve cuts every incumbent's weight to 1/N, so EVERY addition lost and the tool could only
ever say "leave it alone". It was measuring the weighting scheme, not the composition. Scoring
each composition at ITS OWN optimum is the honest comparison, because production will optimise
weights; a candidate that only wins by being given no weight now shows up AS a weight of zero.

ADVISORY, AND THE BASIS IS BACKTEST. Measured 2026-09-01, the 18 sleeves carrying forward
evidence have between 1 and 4 days each -- nowhere near enough to estimate an annual rate, so
the growth numbers here come from the daily-R matrix and are a PRIOR, not a measurement. Forward
coverage is printed beside every sleeve precisely so a composition that looks good on backtest
and has no forward evidence cannot be mistaken for one that has earned it. Nothing here moves
capital; it produces a ranking a human or the promoter can act on.

WHAT `pf_allocator.py` DOES INSTEAD. The allocator solves for the best book over the whole
universe at once, which is the operating decision. This answers the narrower question a person
actually asks -- "what happens if I swap THIS sleeve for THAT one" -- and prints the swap table
the allocator's single answer cannot show.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for p in (str(ROOT), str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = DESK / "reports" / "book_growth_comparison.json"

#: Trading days per year, for annualising a daily log-growth rate.
YEAR = 252
#: Compositions are capped so the union search cannot explode combinatorially on a wide docket.
#: Each composition costs one solve, so this is a runtime budget, not a modelling choice.
MAX_CANDIDATES = 25

#: The heat law, imported rather than restated (gateway_config_fallback is the definition).
try:
    from mt5desk.gateway_config_fallback import HEAT_HARD_CEILING as HARD
    from mt5desk.gateway_config_fallback import HEAT_TARGET as TARGET
    from mt5desk.gateway_config_fallback import MAX_SLEEVE_HEAT_SHARE as SLEEVE_SHARE
except Exception:                                          # pragma: no cover - desk absent
    HARD, TARGET, SLEEVE_SHARE = 0.30, 0.20, 0.25

SLEEVE_CAP = SLEEVE_SHARE * TARGET
#: A 3-sleeve book cannot spend a 20% budget under a 5% per-sleeve cap, so the bound is relaxed
#: to whatever an equal split needs -- otherwise the comparison refuses to score the very book
#: the desk is running today, and "cannot be scored" would read as "scores badly".
MIN_SLEEVE_SHARE = 1.0 / 3.0


def _evidence(daily: pd.DataFrame, cols: list[str]) -> list:
    """SleeveEvidence for `cols`, with mechanism families so the posterior pools correctly."""
    from libs.portfolio.robust_elog import SleeveEvidence

    out = []
    for c in cols:
        parts = str(c).split("_")
        fam = ("session_bracket" if str(c).startswith("gold_") or parts[-1].endswith("DAY")
               else "_".join(parts[1:-1]) or "unspecified")
        out.append(SleeveEvidence(name=str(c), daily_r=daily[c].fillna(0.0).to_numpy(float),
                                  family=fam, symbol=parts[0], cost_r=0.05))
    return out


def annual_growth(daily: pd.DataFrame, cols: list[str], heat: float, cfg: object) -> dict:
    """Annualised robust E[log W] of `cols` at ITS OWN optimal weights, spending `heat` in total.

    Every composition is judged the way the desk would actually run it: total heat pinned to the
    utilisation target, per-sleeve heat bounded, weights solved. See the module header for why
    equal weighting -- the obvious-looking alternative -- measures the weighting scheme instead.
    """
    from libs.portfolio.robust_elog import optimise

    if not cols:
        return {"n_sleeves": 0, "annual_growth_pct": 0.0, "daily_logret": 0.0,
                "cvar_logret": 0.0, "prob_annual_loss": 1.0, "weights": {}}
    ev = _evidence(daily, cols)
    bound = max(heat / max(len(cols), 1), MIN_SLEEVE_SHARE * heat)
    r = optimise(ev, hard_cap=HARD, target=heat, cfg=cfg, max_per_sleeve=max(bound, SLEEVE_CAP))
    return {
        "n_sleeves": len(cols),
        "daily_logret": round(r.mean_log_growth, 8) if np.isfinite(r.mean_log_growth) else None,
        "cvar_logret": round(r.cvar_log_growth, 8) if np.isfinite(r.cvar_log_growth) else None,
        "annual_growth_pct": (round(r.annual_growth_pct, 2)
                              if np.isfinite(r.annual_growth_pct) else float("-inf")),
        "prob_annual_loss": r.prob_annual_loss,
        "total_heat": round(r.total_heat, 6),
        "weights": {k: round(v, 6) for k, v in
                    sorted(r.heat.items(), key=lambda kv: -kv[1]) if v > 1e-6},
    }


def mean_abs_corr(daily: pd.DataFrame, col: str, others: list[str]) -> float:
    """How duplicated `col` is against the book -- the number Sharpe-ranking ignores."""
    if not others:
        return 0.0
    c = daily[[col, *others]].fillna(0.0).corr().iloc[0, 1:]
    v = c.abs().to_numpy(dtype=float)
    v = v[np.isfinite(v)]
    return round(float(v.mean()), 4) if v.size else 0.0


def forward_days() -> dict[str, int]:
    """Days of FORWARD evidence per sleeve -- the confidence column, never an input to growth."""
    try:
        from portfolio_evidence import daily_series
        return {k: len(v) for k, v in daily_series().items()}
    except Exception:
        return {}


def load_book() -> tuple[pd.DataFrame, list[str], list[str]]:
    """The daily-R matrix, the sleeves holding capital today, and the certified candidates.

    CURRENT is read from the gateway's own sleeve set, not from a list here -- a second list of
    "what is live" is exactly the drift `allocation.py`'s header suffered. Whatever the gateway
    would emit on its next pass IS the current book, gold retirements included.
    """
    from research.portfolio_projection import build_daily, build_sleeves, h18_survivor_sleeves

    sleeves = build_sleeves()
    h18, _excluded = h18_survivor_sleeves()
    sleeves += h18
    daily = build_daily(sleeves)

    live: list[str] = []
    try:
        from mt5desk.gateway import sleeve_set
        live = [str(s["name"]) for s in sleeve_set()]
    except Exception:
        # MetaTrader5 is absent on the research box. Fall back to the gold names the promoter
        # knows, minus anything it has retired -- same answer, no terminal required.
        try:
            from research.promoter import GOLD_SLEEVE_NAMES, _load_gold_retired
            retired = set(_load_gold_retired())
            live = [n for n in GOLD_SLEEVE_NAMES if n not in retired]
        except Exception:
            live = []

    cols = list(daily.columns)
    current = [c for c in cols if c in set(live)]
    candidates = [c for c in cols if c not in set(current)]
    return daily, current, candidates


def compositions(daily: pd.DataFrame, current: list[str], candidates: list[str],
                 heat: float, cfg: object) -> list[dict]:
    """Every composition worth comparing, scored on one number.

    The swap arm is the one that matters and the one nothing else in the desk computes: it is
    the only place a certified sleeve can DISPLACE a live one rather than queue behind it.
    """
    fwd = forward_days()
    rows: list[dict] = []

    base = annual_growth(daily, current, heat, cfg)
    rows.append({"composition": "current", "kind": "current", "sleeves": current,
                 "added": None, "dropped": None, **base,
                 "forward_days": {c: fwd.get(c, 0) for c in current}})
    base_g = base["annual_growth_pct"]

    # Weakest current sleeve BY MARGINAL CONTRIBUTION, not by its own Sharpe: the sleeve worth
    # dropping is the one the book misses least, which is a different question from the one that
    # scores worst alone. A hedge can score badly and still be the most valuable member.
    worst, worst_loss = None, np.inf
    for c in current:
        without = annual_growth(daily, [x for x in current if x != c], heat, cfg)
        loss = base_g - without["annual_growth_pct"]
        if loss < worst_loss:
            worst, worst_loss = c, loss

    for cand in candidates[:MAX_CANDIDATES]:
        add = annual_growth(daily, [*current, cand], heat, cfg)
        rows.append({"composition": f"+{cand}", "kind": "add", "sleeves": [*current, cand],
                     "added": cand, "dropped": None,
                     "delta_vs_current_pct": round(add["annual_growth_pct"] - base_g, 2),
                     "mean_abs_corr_to_book": mean_abs_corr(daily, cand, current),
                     "forward_days_added": fwd.get(cand, 0), **add})
        if worst is not None and worst != cand:
            swapped = [x for x in current if x != worst] + [cand]
            sw = annual_growth(daily, swapped, heat, cfg)
            rows.append({"composition": f"-{worst} +{cand}", "kind": "swap", "sleeves": swapped,
                         "added": cand, "dropped": worst,
                         "delta_vs_current_pct": round(sw["annual_growth_pct"] - base_g, 2),
                         "mean_abs_corr_to_book": mean_abs_corr(daily, cand, current),
                         "forward_days_added": fwd.get(cand, 0), **sw})

    union = current + candidates[:MAX_CANDIDATES]
    if union != current:
        un = annual_growth(daily, union, heat, cfg)
        rows.append({"composition": "union", "kind": "union", "sleeves": union,
                     "added": None, "dropped": None,
                     "delta_vs_current_pct": round(un["annual_growth_pct"] - base_g, 2), **un})

    rows.sort(key=lambda r: r["annual_growth_pct"], reverse=True)
    return rows


def main() -> int:
    from libs.portfolio.robust_elog import WorldConfig

    # ONE population for every composition. Scoring each against its own draw would let a
    # composition win by having been handed a kinder set of worlds.
    cfg = WorldConfig(n_worlds=128, n_rows=256, seed=11)
    daily, current, candidates = load_book()
    if not current:
        print("no current book: the gateway emitted no sleeves and the promoter knows no gold "
              "names. UNMEASURED, not zero -- refusing to rank against an empty baseline.")
        return 2
    rows = compositions(daily, current, candidates, TARGET, cfg)
    base = next(r for r in rows if r["kind"] == "current")
    best = rows[0]

    print(f"heat={TARGET:.1%} (cap {HARD:.0%})   rows={len(daily)}   "
          f"sleeves priced={len(daily.columns)}   worlds={cfg.n_worlds}")
    print(f"current book ({len(current)}): {', '.join(current)}")
    print(f"\n{'composition':<44} {'ann%':>9} {'d vs now':>9} {'corr':>6} {'fwd':>5}")
    for r in rows[:25]:
        g = r["annual_growth_pct"]
        print(f"{r['composition'][:44]:<44} {g:9.2f} "
              f"{r.get('delta_vs_current_pct', 0.0):9.2f} "
              f"{r.get('mean_abs_corr_to_book', 0.0):6.3f} "
              f"{r.get('forward_days_added', ''):>5}")

    verdict = ("LEAVE IT ALONE" if best["kind"] == "current"
               else f"{best['kind'].upper()}: {best['composition']}")
    print(f"\nbest composition: {verdict}  "
          f"({best['annual_growth_pct']:.2f}% vs {base['annual_growth_pct']:.2f}% now)")
    if best["kind"] != "current" and best.get("forward_days_added", 0) < 5:
        print("  CONFIDENCE: the winning change rests on a sleeve with "
              f"{best.get('forward_days_added', 0)} days of forward evidence. This is a backtest "
              "prior, not a measurement -- treat it as a research ranking, not an instruction.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_utc": datetime.now(UTC).isoformat(),
        "heat": TARGET, "hard_ceiling": HARD,
        "basis": "backtest daily-R matrix, robust E[log W] at each composition's own optimum",
        "advisory": True,
        "current": current, "n_candidates_scored": min(len(candidates), MAX_CANDIDATES),
        "best": best["composition"], "best_kind": best["kind"],
        "rows": rows,
    }, indent=2, default=str), encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
