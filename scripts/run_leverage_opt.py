"""Recompute dynamic leverage for every deployed/paper sleeve + the joint portfolio.

Reads the live forward return streams (molded curve = cash-carry, perp shadow equity = perp book),
the regime multiplier, and execution reliability, then runs `libs.risk.dynamic_leverage`. Writes:
  * web/leverage.json          -- dashboard: per-sleeve + joint leverage, endogenous caps, bindings
  * data/leverage_target.json  -- the executor reads this to size deployed notional dynamically

Honest by construction: on day-0 / thin data the confidence term is 0, so the recommendation sits at
the floor and only earns leverage as forward validation accrues. Run every cycle (cheap).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.risk.dynamic_leverage import optimize_portfolio, optimize_sleeve

_CURVE = Path("data/live_combined_state.json")
_LEV_WEB = Path("web/leverage.json")
_LEV_TGT = Path("data/leverage_target.json")
_BASE_PER_LEG = 5000.0
# GAP #14 MEASUREMENT FIX (2026-07-23, safe under quarantine -- the executor ignores this
# file in both directions until the ladder re-enable gate). Root cause of incidents #2 and
# the 07-18 under-deploy: confidence fed by the funding-smoothed MOLDED curve (variance
# collapse -> Sharpe 16-24 phantom) and a fwd_days counter that survived incident resets.
# Honest inputs now: the 8h-block challenger series (basis-MtM variance INCLUDED, vif~1)
# and its true block count. PLAUSIBILITY RAIL: an annualized forward Sharpe above
# _PLAUSIBLE_SHARPE is treated as a measurement defect -> confidence 0 + flag (a Sharpe of
# 16 must freeze sizing, never activate it). CLEAN-DAY COUNTER: leverage_target.json now
# carries clean_since -- the start of continuous honest-input operation -- so ladder step 1
# (gap-14 fixed + 30 uncontaminated days) is measurable from a file read.
_PLAUSIBLE_SHARPE = 4.0
_SHADOW_8H = Path("web/cashcarry_shadow_8h.json")


def _load(p: Path, d: object = None) -> object:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d if d is not None else {}


def _rets_from_equity(eq: list[float]) -> np.ndarray:
    a = np.asarray([float(x) for x in eq], dtype="float64")
    if len(a) < 2:
        return np.array([], dtype="float64")
    return a[1:] / a[:-1] - 1.0


def _hourly(curve: list[list[object]]) -> list[float]:
    buckets: dict[str, float] = {}
    for t, e in curve:
        buckets[str(t)[:13]] = float(e)               # last obs per UTC hour
    return [buckets[k] for k in sorted(buckets)]


def main() -> None:
    cs = _load(_CURVE, {})
    cc_eq = _hourly(cs.get("mcurve", []))             # cash-carry molded, hourly (noise-reduced)
    cc_rets = _rets_from_equity(cc_eq)

    sh = _load(Path("web/crypto_shadow.json"), {})
    # forward-only equity (fwd=True) so confidence stays honest -- never counts backtest as proven
    perp_eq = [float(p["v"]) for p in sh.get("equity", [])
               if isinstance(p, dict) and p.get("fwd") and "v" in p]
    perp_rets = _rets_from_equity(perp_eq) if len(perp_eq) > 1 else np.array([])

    ccsh = _load(Path("web/cashcarry_shadow.json"), {})
    regime = _load(Path("web/regime_engine.json"), {})
    regime_mult = float(regime.get("leverage_multiplier", 1.0) or 1.0)

    # execution reliability: fresh executor heartbeat -> 1.0, else haircut (degraded fills/uptime)
    hb = Path("data/cashcarry_exec_heartbeat")
    exec_ok = hb.exists() and (datetime.now(tz=UTC).timestamp() - hb.stat().st_mtime) < 180
    exec_rel = 1.0 if exec_ok else 0.5

    decisions = {}
    sh8 = _load(_SHADOW_8H, {})
    fwd_sharpe_in = float(sh8.get("forward_ann_sharpe_8h",
                                  ccsh.get("forward_ann_sharpe", 0.0)) or 0.0)
    fwd_days_in = float(sh8.get("forward_days_equiv",
                                ccsh.get("forward_days", 0)) or 0)
    implausible = fwd_sharpe_in > _PLAUSIBLE_SHARPE
    if implausible:                     # measurement defect, never evidence of edge
        fwd_sharpe_in = 0.0
    decisions["cash_and_carry"] = optimize_sleeve(
        "cash_and_carry", cc_rets,
        fwd_sharpe=fwd_sharpe_in,
        fwd_days=fwd_days_in,
        regime_mult=regime_mult, exec_reliability=exec_rel,
        liquidity_haircut=0.9, drawdown_ruin=0.35,    # small-cap perps -> slippage/impact haircut
    )
    if len(perp_rets) > 1:
        decisions["perp_ls"] = optimize_sleeve(
            "perp_ls", perp_rets,
            fwd_sharpe=float(sh.get("forward_ann_sharpe", 0.0) or 0.0),
            fwd_days=float(sh.get("forward_days", 0) or 0),
            regime_mult=regime_mult, exec_reliability=exec_rel,
            liquidity_haircut=0.85, drawdown_ruin=0.30,   # directional book -> tighter ruin def
        )

    sleeve_rets = {"cash_and_carry": cc_rets}
    if len(perp_rets) > 1:
        sleeve_rets["perp_ls"] = perp_rets
    joint = optimize_portfolio(sleeve_rets, decisions)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "regime": regime.get("regime"), "regime_mult": regime_mult, "exec_reliability": exec_rel,
        "sleeves": {k: v.to_dict() for k, v in decisions.items()},
        "portfolio": joint,
        "policy": ("Leverage is a continuously optimized control variable. Ceiling is endogenous = "
                   "min(diminishing-returns argmax of E[log], largest L with risk-of-ruin<=2%). "
                   "Confidence (uncertainty shrinkage) gates it to floor until forward-validated."),
    }
    _LEV_WEB.write_text(json.dumps(out, indent=2), "utf-8")

    # executor target: notional/leg = recommended x equity. OVERRIDES --capital only when the
    # optimizer has confidence>0 (edge proven enough) -- day-0 keeps the operator's --capital.
    cc = decisions["cash_and_carry"]
    prev = _load(_LEV_TGT, {})
    # clean_since counts days of HONEST-PIPELINE operation (ladder step-1 clock). The rail
    # firing on an implausible reading IS clean operation -- the pipeline detected and
    # zeroed a bad measurement instead of sizing on it. Only a source change resets it.
    clean_since = (prev.get("clean_since")
                   if prev.get("confidence_source") == "8h_challenger_honest"
                   else out["updated"]) or out["updated"]
    _LEV_TGT.write_text(json.dumps({
        "updated": out["updated"], "sleeve": "cash_and_carry",
        "confidence_source": "8h_challenger_honest",
        "plausibility_rail_fired": bool(implausible),
        "clean_since": clean_since,
        "leverage": round(cc.recommended, 3), "confidence": cc.confidence,
        "notional_per_leg": round(cc.recommended * _BASE_PER_LEG, 2),
        "active": cc.confidence > 0.0,               # executor honours it only when True
        # back-compat superset for run_crypto_testnet / run_capital_plan (supersedes fixed-cap)
        "gated_leverage": round(cc.recommended, 3),
        "growth_optimal": round(cc.growth_optimal, 3), "ruin_cap": round(cc.ruin_cap, 3),
        "status": "DYNAMIC (validated)" if cc.confidence > 0 else "DYNAMIC (floor, unproven)",
    }, indent=2), "utf-8")

    print(f"leverage-opt: cash_and_carry rec={cc.recommended:.3f}x conf={cc.confidence} "
          f"(growth-opt {cc.growth_optimal:.2f}x ruin-cap {cc.ruin_cap:.2f}x {cc.binding}) "
          f"| joint {joint.get('joint_leverage')}x | active={cc.confidence > 0}")


if __name__ == "__main__":
    main()
