"""Aggregate every research run into one honest scoreboard for the dashboard (web/strategies.json).

Reads the reports each runner already wrote; no recomputation, no embellishment. Crypto strategies
appear alongside FX so the dashboard shows the full, truthful research record incl. the cross-
sectional funding candidate that is in forward shadow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPORTS = Path("reports")
_OUT = Path("web/strategies.json")


def _read(*parts: str) -> Any:
    p = _REPORTS.joinpath(*parts)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _survivors(report: Any) -> int:
    if isinstance(report, dict) and isinstance(report.get("survivors"), list):
        return len(report["survivors"])
    return 0


def main() -> None:
    rows: list[dict[str, Any]] = []

    # FX directional (lake research)
    fx = _read("research_lake", "survivor_report.json")
    if fx is not None:
        rows.append({"name": "FX directional", "universe": "7 USD majors (26y)",
                     "best_sharpe": None, "survivors": _survivors(fx),
                     "status": "REJECTED (gauntlet)"})

    # Crypto single-name funding (reversal/carry; last crypto_research run)
    cr = _read("crypto_research", "survivor_report.json")
    if cr is not None:
        rows.append({"name": "Crypto funding (single-name)", "universe": "10-130 perps",
                     "best_sharpe": None, "survivors": _survivors(cr),
                     "status": "REJECTED (fragility/DSR)"})

    # Prediction markets
    pm = _read("prediction_markets", "report.json")
    if isinstance(pm, dict):
        rows.append({"name": "Prediction markets (favorite-longshot)",
                     "universe": f"{pm.get('usable_markets', 0)} Polymarket",
                     "best_sharpe": None, "survivors": int(pm.get("survivors", 0)),
                     "status": "REJECTED (negative / data-capped)"})

    # Cross-sectional funding MAX (the candidate)
    xs = _read("xsec_funding_max", "report.json")
    if isinstance(xs, dict) and xs.get("variants"):
        best = max(xs["variants"], key=lambda v: v.get("ann_sharpe", 0))
        rows.append({"name": "Crypto cross-sectional funding (MAX)",
                     "universe": f"{xs.get('perps', 0)} liquid perps (6y)",
                     "best_sharpe": best.get("ann_sharpe"),
                     "survivors": int(xs.get("survivors", 0)),
                     "status": "SHADOW WATCHLIST (8/9 gates; fails Reality Check)"})

    # Crypto-native PORTFOLIO (the crypto factory headline)
    cp = _read("crypto_portfolio", "report.json")
    if isinstance(cp, dict):
        sl = sum(1 for r in cp.get("results", [])
                 if not str(r.get("sleeve")).startswith("portfolio"))
        rows.append({"name": "Crypto-native portfolio (cluster-RP + cov-forecast)",
                     "universe": f"{cp.get('perps', 0)} perps, {sl} sleeves",
                     "best_sharpe": cp.get("headline_sharpe"), "survivors": 0,
                     "status": "SHADOW (unvalidated; ~0.8-1.2 unstable; fails DSR/PBO)"})

    # RETIRED PRODUCERS, RECORD KEPT (R0421, 2026-08-13). scripts/run_mt5_crossasset.py,
    # run_mt5_funding_bridge.py and run_mt5_portfolio.py were deleted: dead by three independent
    # measures (no manifest line, no importer at any depth, already listed DEPRECATED in
    # REPO_MAP). Their reports/ artifacts are FROZEN at 2026-06-21 and will never advance again.
    #
    # The rows are KEPT rather than dropped. These are real rejections of real strategies and the
    # graveyard is sacred (L1.17) -- deleting them would remove true information from a board whose
    # own note calls itself "the honest research record". What was wrong was not the rows but that
    # a frozen artifact rendered identically to a live one, so the status now SAYS it is retired.
    # (mt5_crossasset_shadow below is NOT affected: run_crossasset_shadow.py is live on cron.)
    _RETIRED = " [RETIRED 2026-08-13 -- producer deleted, artifact frozen 2026-06-21]"

    # MT5 cross-asset diversified portfolios (the native-MT5 max-edge search)
    xa = _read("mt5_crossasset", "report.json")
    if isinstance(xa, dict) and xa.get("variants"):
        best = max(xa["variants"], key=lambda v: v.get("ann_sharpe", 0))
        surv = int(xa.get("survivors", 0))
        status = ("REGISTRY (cleared gauntlet)" if surv
                  else "REJECTED (gauntlet)") + _RETIRED
        rows.append({"name": "MT5 cross-asset (momentum/trend/reversal)",
                     "universe": f"{xa.get('symbols', 0)} instruments, 5 asset classes",
                     "best_sharpe": best.get("ann_sharpe"),
                     "survivors": surv, "status": status})

    # MT5 cross-asset trend+momentum combo (best MT5-executable book, in forward shadow)
    cs = _read("mt5_crossasset_shadow", "report.json")
    if isinstance(cs, dict):
        rows.append({"name": "MT5 cross-asset combo (trend+momentum)",
                     "universe": f"{cs.get('symbols', 0)} instruments, MT5-executable",
                     "best_sharpe": cs.get("backtest_ann_sharpe"),
                     "survivors": 1 if cs.get("deployable") else 0,
                     "status": f"SHADOW WATCHLIST ({cs.get('gates_passed', '?')} gates; "
                               "fails PBO/fragility)"})

    # MT5 alpha-portfolio campaign (9 sleeves incl. CFTC COT positioning, risk-parity)
    mp = _read("mt5_portfolio", "report.json")
    if isinstance(mp, dict) and mp.get("results"):
        surv = sum(1 for r in mp["results"] if r.get("survived"))
        sleeves = [r for r in mp["results"] if not str(r.get("sleeve", "")).startswith("portfolio")]
        best = max((r.get("ann_sharpe") or 0) for r in mp["results"])
        status = (f"REGISTRY ({surv} survivors)" if surv
                  else f"REJECTED (best {best} fails DSR/fragility)") + _RETIRED
        rows.append({"name": f"MT5 alpha portfolio ({len(sleeves)} sleeves + COT)",
                     "universe": f"{mp.get('instruments', 0)} instruments, risk-parity",
                     "best_sharpe": best, "survivors": surv, "status": status})

    # Funding-signal -> MT5 crypto-CFD bridge (research globally, execute on MT5)
    br = _read("mt5_funding_bridge", "report.json")
    if isinstance(br, dict) and br.get("variants"):
        best = max(br["variants"], key=lambda v: v.get("ann_sharpe", 0))
        gross = next((s["ann_sharpe"] for s in br.get("financing_sweep", [])
                      if s.get("daily_financing_bps") == 0.0), None)
        rows.append({"name": "Funding signal -> MT5 crypto CFDs (bridge)",
                     "universe": f"{br.get('cfd_names', 0)} MT5 CFDs (gross sharpe {gross})",
                     "best_sharpe": best.get("ann_sharpe"),
                     "survivors": int(br.get("survivors", 0)),
                     "status": "REJECTED (edge is funding cashflow, not price)" + _RETIRED})

    payload = {"strategies": rows,
               "note": "Honest research record. Net-of-cost, full validation. "
                       "Only the cross-sectional funding candidate is alive (in forward shadow)."}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"wrote {_OUT} with {len(rows)} strategies")
    for r in rows:
        print(f"  {r['name']:42} sharpe={r['best_sharpe']} status={r['status']}")


if __name__ == "__main__":
    main()
