"""#6 Alpha Tournament -- sleeves compete for capital; marginal contribution decides the winner.

Joins the registry (web/registry.json) with the meta-portfolio allocator (web/allocation.json): each
alpha's tournament score = marginal Sharpe contribution, penalised by crowding (max correlation) and
rewarded for surviving the gauntlet. Capital share = the allocator's recommended weight. This is the
dynamic-capital-allocation step: capital flows to the sleeves that contribute most at the portfolio
level, not to the highest standalone Sharpe. SHADOW (advisory) -- not applied to live capital.
Writes web/tournament.json.

    python scripts/run_tournament.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_REG = Path("web/registry.json")
_ALLOC = Path("web/allocation.json")
_OUT = Path("web/tournament.json")


def _short(name: str) -> str:
    return name.split("::", 1)[-1]


def main() -> None:
    reg = json.loads(_REG.read_text("utf-8")) if _REG.exists() else {"alphas": []}
    alloc = json.loads(_ALLOC.read_text("utf-8")) if _ALLOC.exists() else {}
    marg = alloc.get("marginal_contribution", {})
    rec = (alloc.get("weights", {}) or {}).get("recommended", {})

    rows = []
    for a in reg.get("alphas", []):
        s = _short(a["name"])
        mc = float(marg.get(s, 0.0) or 0.0)
        corr = float(a.get("max_corr") or 0.0)
        survived = bool(a.get("survived"))
        # tournament score: portfolio contribution, crowding-penalised, survival-rewarded
        score = mc * (1.0 - 0.5 * corr) * (1.5 if survived else 1.0)
        rows.append({"alpha": s, "category": a.get("category"),
                     "marginal_sharpe": round(mc, 3), "max_corr": round(corr, 3),
                     "survived": survived, "capital_share": round(float(rec.get(s, 0.0)), 4),
                     "tournament_score": round(score, 4), "status": a.get("status")})
    rows.sort(key=lambda r: -r["tournament_score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "status": "SHADOW",
        "n_competitors": len(rows),
        "n_positive_contribution": sum(1 for r in rows if r["marginal_sharpe"] > 0),
        "winner": rows[0]["alpha"] if rows else None,
        "results": rows,
        "note": ("capital follows MARGINAL portfolio contribution, not standalone Sharpe; crowding "
                 "penalised, survival rewarded. Advisory -- live capital unchanged."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    pos = out["n_positive_contribution"]
    print(f"tournament: {len(rows)} competitors, {pos} with positive marginal contribution; "
          f"winner={out['winner']}")


if __name__ == "__main__":
    main()
