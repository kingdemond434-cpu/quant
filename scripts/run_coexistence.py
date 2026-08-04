#!/usr/bin/env python3
"""NON-DESTRUCTIVE COEXISTENCE (P16) -- no sleeve, family or engine may cost another its growth.

THE PRINCIPAL'S REQUIREMENT (2026-08-02): systematic and discretionary, every sleeve, every
section -- none may compromise or reduce another's growth, and all reach their own maximum. That
is two separate rules and conflating them loses the harder one.

  NOBODY SUBTRACTS. A strategy is judged by its MARGINAL contribution to the portfolio, never by
  its standalone record: MC_i = E[log W | S] - E[log W | S \\ {i}]. A weaker standalone strategy
  that raises compounding through diversification BEATS a stronger one that raises correlation.
  Ranking sleeves by their own Sharpe builds a book of correlated winners, which is one bet
  wearing five names.

  EVERYBODY MAXES. After the global optimum is secured, every family expands to its own maximum
  feasible point in the residual -- P12's second half, the one that usually gets dropped. A family
  that loses the top slot is second in line this cycle, never defunded, and a family that could
  grow and does not is an optimisation failure rather than a tidy book.

ORTHOGONALITY BEFORE RETIREMENT, ALWAYS IN THAT ORDER. When two families interact badly the loss
is usually in the INTERACTION -- they trade the same liquidity, at the same moment, into the same
book -- and separating execution, timing or capital recovers BOTH. Retiring one recovers the
interaction loss and gives up the strategy, which is strictly worse whenever separation was
available. The desk expands orthogonality before it reduces opportunity, and this organ will not
emit a retirement recommendation until the separation ladder has been tried and measured.

DORMANT UNTIL TWO FAMILIES EXIST, and it says so. MC_i is undefined with one sleeve and
meaningless with none; computing it anyway would produce a confident number about an interaction
that cannot occur. It arms from a DATA condition -- the moment a second family has a performance
record -- so nobody has to remember.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.estimate import MIN_N_FOR_ACTION, Estimate  # noqa: E402
from libs.doctrine.portfolio_law import (  # noqa: E402
    coexistence_verdict,
    marginal_contribution,
    portfolio_entropy,
)

METRICS = ROOT / "data/desk_metrics.sqlite"
OUT = ROOT / "data/coexistence.json"

#: Families must BOTH clear this before any interaction claim is made. One observation of an
#: interaction is an anecdote, and a retirement recommendation built on one would destroy a
#: strategy to fix noise.
MIN_OBS = MIN_N_FOR_ACTION

#: The order in which a harmful interaction is addressed. Retirement is LAST and is never reached
#: by this organ on its own -- it recovers the interaction loss AND gives up the strategy, which
#: is strictly worse whenever any earlier rung was available and untried.
SEPARATION_LADDER = ("execution separation", "timing separation", "capital separation",
                     "signal orthogonalisation", "risk orthogonalisation")


def _families() -> dict[str, list[float]]:
    """family -> per-period contribution series, from the desk's own performance record."""
    if not METRICS.exists():
        return {}
    out: dict[str, list[float]] = {}
    try:
        with sqlite3.connect(f"file:{METRICS}?mode=ro", uri=True) as c:
            cols = {r[1] for r in c.execute("pragma table_info(alpha_performance)")}
            if not cols:
                return {}
            fam = "family" if "family" in cols else ("alpha_id" if "alpha_id" in cols else None)
            val = next((v for v in ("log_return", "ret", "pnl") if v in cols), None)
            if not fam or not val:
                return {}
            q = f"select {fam}, {val} from alpha_performance"  # noqa: S608 -- allowlisted identifiers
            for name, v in c.execute(q):
                if name is not None and isinstance(v, int | float):
                    out.setdefault(str(name), []).append(float(v))
    except sqlite3.Error:
        return {}
    return out


def main() -> int:
    t0 = time.time()
    fams = _families()
    eligible = {k: v for k, v in fams.items() if len(v) >= MIN_OBS}

    if len(eligible) < 2:
        out = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "state": "DORMANT",
            "families_seen": sorted(fams),
            "families_eligible": sorted(eligible),
            "arms_at": f"2 families with >= {MIN_OBS} recorded periods each",
            "note": ("MC_i is undefined with one family and meaningless with none. Computing it "
                     "anyway would produce a confident number about an interaction that cannot "
                     "occur -- and a retirement recommendation built on that would destroy a "
                     "strategy to fix noise. Arms automatically from the performance record; "
                     "nobody has to remember."),
            "policy_active_now": (
                "the ORDER is already binding even while the measurement is dormant: when two "
                "families do interact badly, separation is attempted and MEASURED before any "
                "retirement is considered. Expanding orthogonality before reducing opportunity is "
                "a rule about what to try first, and it does not need data to be in force."),
            "separation_ladder": list(SEPARATION_LADDER),
            "next_ceiling": ("a second family with a performance record; then MC_i per family "
                             "every cycle; then the same test across execution engines and "
                             "venues, which interact through liquidity even when signals do not"),
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"coexistence: DORMANT -- {len(eligible)}/2 eligible families "
              f"({len(fams)} seen). Arms from the performance record.")
        return 0

    total = [sum(vals) for vals in zip(*eligible.values(), strict=False)]
    with_all = Estimate(sum(total) / len(total),
                        (sum((x - sum(total) / len(total)) ** 2 for x in total)
                         / max(1, len(total) - 1)) ** 0.5 / max(1, len(total)) ** 0.5,
                        len(total), "portfolio")

    contributions, maxed = {}, []
    for name in eligible:
        others = [v for k, v in eligible.items() if k != name]
        without = [sum(vals) for vals in zip(*others, strict=False)] if others else [0.0]
        mu = sum(without) / len(without)
        se = ((sum((x - mu) ** 2 for x in without) / max(1, len(without) - 1)) ** 0.5
              / max(1, len(without)) ** 0.5)
        contributions[name] = marginal_contribution(
            with_all, Estimate(mu, se, len(without), f"without {name}"), name)
        # EVERYBODY MAXES: a family that contributes and is not at its own maximum is an
        # optimisation failure, not a tidy book. Reported per family, never only in aggregate.
        if contributions[name]["significant_positive"]:
            maxed.append(name)

    verdict = coexistence_verdict(contributions)
    ent = portfolio_entropy(dict.fromkeys(eligible, 1.0))
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "state": "ACTIVE",
        "seconds": round(time.time() - t0, 2),
        "families": sorted(eligible),
        "contributions": contributions,
        "verdict": verdict,
        "entropy": ent,
        "families_contributing": sorted(maxed),
        "separation_ladder": list(SEPARATION_LADDER),
        "retirement_permitted": False,
        "retirement_note": (
            "this organ NEVER recommends retirement on its own. A harmful interaction is a reason "
            "to separate execution, timing or capital and MEASURE again -- retiring recovers the "
            "interaction loss and gives up the strategy, which is strictly worse whenever an "
            "earlier rung was available and untried."),
        "next_ceiling": ("MC_i per EXECUTION ENGINE and per VENUE, not only per family -- two "
                         "sleeves with orthogonal signals still interact through the same "
                         "liquidity, and that interaction is invisible to a signal-level test"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), "utf-8")
    print(f"coexistence: {verdict['verdict']} across {len(eligible)} families | "
          f"{ent['effective_bets']} effective bets | {len(maxed)} contributing")
    for name, c in contributions.items():
        print(f"  {name:24s} MC={c['mc']:+.6f} {c['note'][:70]}")
    if verdict["harmful"]:
        print(f"  REMEDY ORDER (retirement is LAST and not taken here): "
              f"{' -> '.join(SEPARATION_LADDER)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
