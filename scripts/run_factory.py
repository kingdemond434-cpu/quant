"""Alpha Research Factory state report -- the firm's control panel (extends, does not rebuild).

Consolidates the existing portfolio gauntlet output into the governance view the mission needs:
sleeve leaderboard ranked by PORTFOLIO CONTRIBUTION (not standalone Sharpe), edge-family breadth vs
target, the portfolio-Sharpe milestone path + bottleneck, rejected sleeves turned into research
seeds, and the free-dataset priority queue. Writes web/factory.json for the dashboard.

Honesty: nothing here relaxes a gate or invents a number. Confidence is a backtest proxy until
forward-shadow days accrue (forward evidence dominates, per the mission).

    python scripts/run_factory.py
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

from libs.factory.registry import (
    EDGE_FAMILIES,
    SLEEVE_FAMILY,
    TARGET_PER_FAMILY,
    best_dataset_priorities,
    free_next_priorities,
    milestone_path,
)

_REPORT = Path("reports/mt5_portfolio/report.json")
_WEB = Path("web/factory.json")
_OUT = Path("reports/factory/state.json")
_TARGET_SHARPE = 1.5

# Free research seeds by family -- what to try next when a family is thin (no budget).
_SEEDS = {
    "positioning": "add CFTC disaggregated/TFF (managed-money, leveraged-funds) -- free, cleaner",
    "carry": "accumulate broker-swap log to 250d; add ECB/Treasury rate differentials (free)",
    "macro": "rates_trend live; add yield-curve regime from TLT/IEF/SHY (free ETF lake)",
    "seasonality": "day-of-week / pre-holiday / month effects from the price lake (free, untested)",
    "structural": "curve_rv / credit_rv live; add TLT-LQD, IEF-SHY structural spreads (free)",
    "flow": "sector_rotation live; add ETF lead-lag / RS rotation across SMH/CIBR/SKYY (free)",
    "volatility": "realized-vol breakout / vol-target timing from price (free); true VRP needs "
                  "options (not MT5-executable) -- honest gap",
    "trend": "broaden instruments (free ingest) rather than re-tune existing trend",
    "momentum": "broaden instruments (free ingest) rather than re-tune existing momentum",
    "relative_value": "add cointegration filter; more pairs from the ETF/commodity lake (free)",
}


def _status(sharpe: float, survived: bool) -> str:
    if survived:
        return "DEPLOYABLE (gauntlet) -> shadow then promote"
    if sharpe > 0.5:
        return "SHADOW"
    if sharpe > 0.4:
        return "CANDIDATE"
    return "REJECTED"


def _confidence(sharpe: float, gates: str) -> float:
    try:
        passed, total = (int(x) for x in str(gates).split("/"))
        gate_frac = passed / total
    except ValueError:
        gate_frac = 0.0
    # backtest-only proxy in [0,1]; forward days would raise this (tracked separately by shadow)
    return round(max(0.0, min(sharpe / 0.7, 1.0)) * gate_frac, 2)


def main() -> None:
    if not _REPORT.exists():
        # ITS PRODUCER IS GONE (R0421, 2026-08-13). scripts/run_mt5_portfolio.py was retired as
        # dead MT5-stack code, so this input can never be regenerated and this script cannot run
        # again. Left in place rather than deleted -- it is already on REPO_MAP's DEPRECATED list
        # and cascading deletions past the MT5 chain is a bigger decision than this row -- but the
        # message must not send a reader chasing a path that no longer exists.
        raise SystemExit(
            f"{_REPORT} is absent and its producer (scripts/run_mt5_portfolio.py) was RETIRED "
            "on 2026-08-13 (R0421). This script is deprecated and cannot be re-run.")
    rep = json.loads(_REPORT.read_text("utf-8"))
    results = rep["results"]
    incr = rep.get("incremental_sharpe", {})
    corr = rep.get("correlations", {})
    port_sharpe = float(rep.get("portfolio_ann_sharpe", 0.0))

    # Sleeve leaderboard -- ranked by PORTFOLIO CONTRIBUTION, then standalone Sharpe
    sleeves = [r for r in results if not str(r["sleeve"]).startswith("portfolio")]
    leaderboard = []
    for r in sleeves:
        name = r["sleeve"]
        fam = SLEEVE_FAMILY.get(name, "?")
        sh = float(r.get("ann_sharpe") or 0.0)
        others = corr.get(name, {})
        finite = [abs(v) for k, v in others.items()
                  if k != name and isinstance(v, (int, float)) and math.isfinite(v)]
        avg_abs_corr = round(sum(finite) / len(finite), 2) if finite else None
        leaderboard.append({
            "sleeve": name, "family": fam, "sharpe": sh,
            "contribution": incr.get(name, 0.0), "avg_abs_corr": avg_abs_corr,
            "gates": r.get("gates", ""), "status": _status(sh, bool(r.get("survived"))),
            "confidence": _confidence(sh, str(r.get("gates", "0/9"))),
        })
    leaderboard.sort(key=lambda d: (d["contribution"], d["sharpe"]), reverse=True)

    # Family breadth (count CANDIDATE-quality sleeves, sharpe > 0.4, per family)
    counts = dict.fromkeys(EDGE_FAMILIES, 0)
    present = dict.fromkeys(EDGE_FAMILIES, 0)
    for d in leaderboard:
        f = d["family"]
        if f in counts:
            present[f] += 1
            if d["sharpe"] > 0.4:
                counts[f] += 1
    ms = milestone_path(port_sharpe, counts)

    # Rejections -> seeds
    rejected = [{"sleeve": d["sleeve"], "family": d["family"], "sharpe": d["sharpe"],
                 "seed": _SEEDS.get(d["family"], "investigate mechanism / dataset gap")}
                for d in leaderboard if d["status"] == "REJECTED"]

    # Thin/empty families -> highest-value free research directions
    gaps = sorted(((TARGET_PER_FAMILY - counts[f], f) for f in EDGE_FAMILIES), reverse=True)
    next_research = [{"family": f, "have": counts[f], "target": TARGET_PER_FAMILY,
                      "free_seed": _SEEDS.get(f, "")} for deficit, f in gaps if deficit > 0][:6]

    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "portfolio_sharpe": round(port_sharpe, 3), "target_sharpe": _TARGET_SHARPE,
        "milestone": {"current": ms.current, "next": ms.next_milestone, "gap": ms.gap,
                      "families_complete": ms.families_complete,
                      "families_total": ms.families_total, "bottleneck_family": ms.bottleneck},
        "family_breadth": {f: {"candidates": counts[f], "present": present[f],
                               "target": TARGET_PER_FAMILY} for f in EDGE_FAMILIES},
        "leaderboard": leaderboard,
        "next_research": next_research,
        "rejected_seeds": rejected,
        "datasets_in_use": best_dataset_priorities(top_n=7),
        "free_next_datasets": free_next_priorities(top_n=6),
        "note": "Portfolio metrics dominate strategy metrics. No-budget mode: free data only. "
                "Forward-shadow evidence outranks backtests; confidence rises with shadow days.",
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2, default=str), "utf-8")

    print(f"PORTFOLIO Sharpe {port_sharpe:.2f}  ->  next milestone {ms.next_milestone} "
          f"(gap {ms.gap:+.2f})  | target {_TARGET_SHARPE}")
    print(f"families complete: {ms.families_complete}/{ms.families_total} "
          f"(>= {TARGET_PER_FAMILY} candidate sleeves each) | bottleneck: {ms.bottleneck}")
    print("\nLEADERBOARD by portfolio contribution:")
    for d in leaderboard[:12]:
        print(f"  {d['sleeve']:16} {d['family']:13} sharpe={d['sharpe']:>5} "
              f"contrib={d['contribution']:>+5} corr~{d['avg_abs_corr']} {d['status']}")
    print("\nFREE next-research (thin families):")
    for nr in next_research:
        print(f"  {nr['family']:13} have {nr['have']}/{nr['target']}: {nr['free_seed'][:80]}")


if __name__ == "__main__":
    main()
