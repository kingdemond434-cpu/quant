"""EXECUTION INTELLIGENCE LAYER -- one consolidated read over every execution organ (triage #102).

Principal-approved design 2026-07-29, with the principal's own amendment kept verbatim in force:
monitor -> diagnose -> recommend -> adjust ONLY within approved limits; this layer NEVER edits
execution logic or parameters itself. Execution is where small mistakes lose money immediately,
so the layer's entire write surface is one JSON report and (optionally) a page.

WHY A CONSOLIDATION AND NOT A NEW AGENT: the desk already owns the sensors --
  hedge_integrity.py         -> data/hedge_integrity.json        (the incident-#6 invariant)
  execution_bottleneck.py    -> data/execution_bottleneck.json   (gate-vs-book, cost truth)
  run_trade_forensics.py     -> web/trade_forensics.json         (churn/baseline/leg-thrash classes)
  run_cost_model.py          -> data/cost_model.json             (measured book-walk slippage)
  executor TCA fields        -> data/cashcarry_trades.json       (fills, fees, hold times)
Each fires alone; NOTHING reads them together, so a degradation that is obvious across two feeds
(e.g. rising realized cost while the cost model says cheap = execution drift) was invisible.
Per L2.9 the fix is a merge, not an agent. Verdicts per surface: OK / DEGRADED / CRITICAL / NO-DATA
-- NO-DATA is a real verdict (fail-loud), never silently skipped (the health.json fail-open
lesson, DESK_BRIEF known-blockers).

Runs from the daily cycle + cron; pure stdlib; every input read defensively (VPS-side files).

    python scripts/run_execution_intel.py [--page]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/execution_intel.json")

# Approved-limits contract (the principal's amendment, mechanical form): this layer may only
# RECOMMEND values for these executor knobs, and only inside these bounds. Anything outside the
# bound, or any knob not listed, is a RECOMMEND-TO-HUMAN, never an auto-adjust. Applying a
# recommendation remains a separate, logged, human-or-executor-owned step.
_APPROVED_LIMITS: dict[str, tuple[float, float]] = {
    "_DEFAULT_RT_BPS": (4.5, 80.0),     # entry-gate cost bar (bps): floor=measured p50 era, cap sane
    "_MIN_HOLD_H": (8.0, 72.0),         # min hold: never below one funding period
}


def _read(path: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(Path(path).read_text("utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _age_h(obj: dict[str, Any] | None, *keys: str) -> float | None:
    if not obj:
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str):
            try:
                ts = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return (datetime.now(tz=UTC) - ts).total_seconds() / 3600.0
            except ValueError:
                continue
    return None


def _surface_hedge(report: dict[str, Any]) -> None:
    hi = _read("data/hedge_integrity.json")
    if hi is None:
        report["hedge_integrity"] = {"verdict": "NO-DATA",
                                     "detail": "data/hedge_integrity.json unreadable"}
        return
    bad = [s for s, st in (hi.get("legs") or {}).items()
           if str(st.get("state", "")).upper() in ("INVERTED", "MISSING", "MISMATCHED")]
    report["hedge_integrity"] = {
        "verdict": "CRITICAL" if bad else "OK", "bad_legs": bad,
        "age_h": _age_h(hi, "updated", "ts"),
        "detail": f"{len(bad)} leg(s) violating the carry invariant" if bad else "all legs hedged",
    }


def _surface_forensics(report: dict[str, Any]) -> None:
    tf = _read("web/trade_forensics.json")
    if tf is None:
        report["trade_forensics"] = {"verdict": "NO-DATA",
                                     "detail": "web/trade_forensics.json unreadable"}
        return
    bleeding = [k for k, v in tf.items()
                if isinstance(v, dict) and isinstance(v.get("net"), (int, float)) and v["net"] < 0
                and isinstance(v.get("n"), int) and v["n"] >= 10]
    report["trade_forensics"] = {
        "verdict": "DEGRADED" if bleeding else "OK", "bleeding_classes": bleeding,
        "age_h": _age_h(tf, "updated", "ts"),
    }


def _surface_cost_drift(report: dict[str, Any]) -> None:
    """Execution drift = realized cost trend vs the measured cost model -- the cross-feed check
    no single organ could make. Uses trade-log fee+slip per round-trip vs cost_model prediction."""
    cm, trades = _read("data/cost_model.json"), None
    try:
        raw = json.loads(Path("data/cashcarry_trades.json").read_text("utf-8"))
        trades = raw if isinstance(raw, list) else raw.get("trades")
    except (OSError, json.JSONDecodeError):
        pass
    if cm is None or not trades:
        report["cost_drift"] = {"verdict": "NO-DATA",
                                "detail": "needs data/cost_model.json + data/cashcarry_trades.json"}
        return
    tail = [t for t in trades[-50:] if isinstance(t, dict)]
    realized = [t.get("rt_bps") or t.get("cost_bps") for t in tail]
    realized = [float(x) for x in realized if isinstance(x, (int, float))]
    if len(realized) < 10:
        report["cost_drift"] = {"verdict": "NO-DATA",
                                "detail": f"only {len(realized)} trades carry TCA cost fields yet"}
        return
    med = sorted(realized)[len(realized) // 2]
    syms = cm.get("symbols") or {}
    preds = []
    for s in syms.values():
        try:
            p = s["fut_sell"]["500"]["median_bps"]
            if p is not None:
                preds.append(float(p))
        except (KeyError, TypeError, ValueError):
            continue
    pred_med = sorted(preds)[len(preds) // 2] if preds else None
    drift = (med / pred_med) if pred_med else None
    verdict = "OK"
    if drift is not None and drift > 2.0:
        verdict = "DEGRADED"          # paying >2x the modeled cost = model or execution drifted
    if drift is not None and drift > 4.0:
        verdict = "CRITICAL"
    report["cost_drift"] = {"verdict": verdict, "realized_median_bps": round(med, 2),
                            "modeled_median_bps": round(pred_med, 3) if pred_med else None,
                            "realized_over_modeled": round(drift, 2) if drift else None,
                            "n_trades": len(realized)}


def _surface_bottleneck(report: dict[str, Any]) -> None:
    eb = _read("data/execution_bottleneck.json")
    if eb is None:
        report["bottleneck"] = {"verdict": "NO-DATA",
                                "detail": "data/execution_bottleneck.json unreadable"}
        return
    report["bottleneck"] = {"verdict": "OK", "age_h": _age_h(eb, "updated", "ts"),
                            "summary": {k: eb[k] for k in list(eb)[:6]}}


def _recommend(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Diagnose -> recommend. Recommendations carry the approved-limit bound they must respect;
    nothing here writes to executor state. A recommendation outside every bound is escalation."""
    recs: list[dict[str, Any]] = []
    cd = report.get("cost_drift", {})
    if cd.get("verdict") in ("DEGRADED", "CRITICAL") and cd.get("realized_median_bps"):
        lo, hi = _APPROVED_LIMITS["_DEFAULT_RT_BPS"]
        target = min(max(float(cd["realized_median_bps"]), lo), hi)
        recs.append({"knob": "_DEFAULT_RT_BPS", "action": "raise-to-realized",
                     "target_bps": round(target, 1), "bound": [lo, hi],
                     "why": "realized round-trip cost exceeds model "
                            f"{cd.get('realized_over_modeled')}x -- entry gate must price reality",
                     "auto_apply": False})
    if report.get("hedge_integrity", {}).get("verdict") == "CRITICAL":
        recs.append({"knob": None, "action": "PAGE+PAUSE-OPENS",
                     "why": "hedge invariant violated -- incident-#6 signature",
                     "auto_apply": False})
    return recs


def main() -> int:
    report: dict[str, Any] = {"updated": datetime.now(tz=UTC).isoformat(),
                              "design": "monitor->diagnose->recommend; never self-applies"}
    _surface_hedge(report)
    _surface_forensics(report)
    _surface_cost_drift(report)
    _surface_bottleneck(report)
    report["recommendations"] = _recommend(report)
    verdicts = [v.get("verdict") for v in report.values() if isinstance(v, dict) and "verdict" in v]
    report["overall"] = ("CRITICAL" if "CRITICAL" in verdicts else
                         "DEGRADED" if "DEGRADED" in verdicts else
                         "NO-DATA" if verdicts and all(x == "NO-DATA" for x in verdicts) else "OK")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2), "utf-8")
    parts = ", ".join(f"{k}={v['verdict']}" for k, v in report.items()
                      if isinstance(v, dict) and "verdict" in v)
    print(f"execution intel: {report['overall']} ({parts})")
    for r in report["recommendations"]:
        print(f"  RECOMMEND {r.get('knob') or r['action']}: {r['why']}")
    if "--page" in sys.argv and report["overall"] == "CRITICAL":
        return 2   # caller (run_alerts / cron wrapper) owns delivery; exit code is the signal
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
