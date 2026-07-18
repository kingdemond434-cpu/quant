"""GROWTH AUDIT -- the anti-conservatism engine: under-utilization of AUTHORIZED size is a DEFECT.

Every risk system asks "are we too big?"; nothing asks "are we too SMALL?" -- so conservatism
accretes silently (floors outlive their reason, capital idles, ramps stall) and geometric growth
is quietly compromised. This engine runs daily and flags every gap between what the evidence
AUTHORIZES and what is actually DEPLOYED. Each gap must carry a justification of exactly one of:
  evidence  -- the gate is honestly unproven (e.g. leverage floored at confidence=0)  -> OK
  survival  -- a ruin/concentration/black-swan constraint binds                        -> OK
  human     -- waiting on a one-time human act (live keys, VPS)                        -> SURFACE
  NONE      -- no valid reason                                    -> CONSERVATISM DEFECT: close it
Feed-only (no venue calls) -> cheap every cycle. Emits web/growth_audit.json; the CRO cycle must
close every NONE-gap same-cycle or ledger-justify it (deferral discipline applies).

    python scripts/run_growth_audit.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/growth_audit.json")
_UTIL_TARGET = 0.75          # deployed/(deployed+idle spot USDT) below this -> investigate


def _load(p: str) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(Path(p).read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def _num(v: object, d: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return d


def main() -> None:
    lc = _load("web/live_combined.json")
    cc = _load("web/cashcarry_live.json")
    lv = _load("web/leverage.json")
    pol = _load("data/live_deployment_policy.json")
    items: list[dict[str, Any]] = []

    # 1) CAPITAL UTILIZATION vs AUTHORIZED capital (2026-07-18 fix: the old denominator was
    # the RAW spot USDT wallet -- on a faucet-fed testnet that is not authorized capital, and
    # after the 07-17 hygiene sweep (~$99.5k consolidated) it made this defect a permanent
    # phantom whose "remediation" was the leverage-runaway class through the back door.
    # Utilization = deployed / the operator's authorized capital (config). Idle wallet is
    # surfaced as INFO for the principal: AUTHORIZING more is a principal/gate decision,
    # never an audit demand.
    dep = _num(cc.get("deployed_notional"))
    idle = _num(lc.get("spot", {}).get("usdt"))
    try:
        authorized = _num(_load("data/cashcarry_config.json").get("capital")) or 4500.0
    except Exception:
        authorized = 4500.0
    util = round(dep / authorized, 3) if authorized > 0 else None
    items.append({
        "check": "carry_capital_utilization",
        "utilized": f"${dep:,.0f} deployed", "authorized": f"${authorized:,.0f} authorized "
        f"(config) | wallet idle ${idle:,.0f} (info: raising authorized capital is a "
        "principal decision)",
        "utilization": util,
        "verdict": ("OK" if util is None or util >= _UTIL_TARGET else "GAP"),
        "justified_by": ("fully deployed to the authorized ceiling"
                         if util is not None and util >= _UTIL_TARGET else
                         "NONE -- authorized capital is not fully deployed: the executor "
                         "should be using its full config capital (check free-capital sizing "
                         "/ open blocks)"),
    })

    # 2) LEVERAGE vs the growth-optimal target: floored is OK ONLY while confidence == 0.
    sl = lv.get("sleeves", {}).get("cash_and_carry", {})
    conf = _num(sl.get("confidence"))
    rec = _num(sl.get("recommended_leverage"))
    actual_lev = 1.0
    lev_gap = conf > 0 and rec > actual_lev * 1.1
    items.append({
        "check": "leverage_vs_growth_optimal",
        "utilized": f"{actual_lev:g}x", "authorized": f"recommended {rec:g}x @ conf {conf:g} "
        f"(ruin cap {_num(sl.get('ruin_cap')):g}x)",
        "verdict": "GAP" if lev_gap else "OK",
        "justified_by": ("NONE -- validation confidence is positive but sizing has not ramped: "
                         "the auto-ramp MUST engage (this is the defect class the audit exists for)"
                         if lev_gap else
                         "evidence (confidence=0: floored on unproven edge is honest, not timid)"),
    })

    # 3) LIVE DEPLOYMENT readiness: armed policy waiting only on the one-time human setup.
    armed = str(pol.get("status", "")).startswith("ARMED")
    items.append({
        "check": "live_deployment_path",
        "utilized": "testnet only", "authorized": "auto-deploy ARMED (Kelly-unit ladder)",
        "verdict": "HUMAN-PENDING" if armed else "GAP",
        "justified_by": ("human (one-time: live account + trade-only keys + deposit + VPS -- "
                         "surface until done; every validated day without it is foregone growth)"
                         if armed else "NONE -- policy not armed"),
    })

    # 4) VALIDATION THROUGHPUT: every fast-track-eligible sleeve must be promoted same-day.
    sh = _load("web/cashcarry_shadow.json")
    ft = str(sh.get("fast_track", ""))
    items.append({
        "check": "promotion_latency",
        "utilized": ft or "n/a", "authorized": "promote the DAY eligibility hits (40d + t>=1.65)",
        "verdict": "OK" if not ft.startswith("ELIGIBLE") else "ACT-NOW",
        "justified_by": "evidence clock" if not ft.startswith("ELIGIBLE")
        else "NONE -- eligible sleeve not promoted = pure foregone growth",
    })

    defects = [i["check"] for i in items if str(i["justified_by"]).startswith("NONE")]
    out = {"updated": datetime.now(tz=UTC).isoformat(), "items": items,
           "conservatism_defects": defects,
           "rule": ("every NONE-gap is a DEFECT: close it same-cycle or ledger-justify it. "
                    "Floors are for missing evidence, never for comfort. Conservatism beyond "
                    "survival constraints is a cost to lifetime geometric growth.")}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"growth audit: {len(defects)} conservatism defect(s)"
          + (f" -> {defects}" if defects else " -- fully deployed to authorized ceilings"))


if __name__ == "__main__":
    main()
