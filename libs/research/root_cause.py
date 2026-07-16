"""Root Cause Engine -- classify every realized loss BEFORE anyone is allowed to react to it.

Institutions don't ask "we're losing, what do we change?" -- they ask "is this loss EXPECTED?"
and act only on evidence. Every PnL deviation is classified into exactly one bucket with a
CONFIDENCE distribution (never a single confident guess), and only three buckets may trigger
autonomous action:

    expected_variance   -> DO NOTHING (the psychologically hard, usually correct answer)
    execution_issue     -> improve execution engine (maker share down, slippage, fees)
    infrastructure_bug  -> fix immediately (orphans, hedge drift, stale collectors)
    model_assumption    -> freeze confidence, audit assumptions (fee/funding schedule changed)
    alpha_decay         -> reduce confidence; retire only if statistically persistent
    regime_shift        -> research, never an immediate production change

HARD RULE (enforced by the verdict): no strategy parameter may be modified from realized PnL
alone -- degradation must be statistically significant AND root-caused. Also computes the
IMPLEMENTATION SHORTFALL chain (expected edge -> after fees -> realized) so the missing bps are
attributable, and TRACKING ERROR (expected vs actual PnL) so raw red numbers stop driving action.
Pure/stdlib + deterministic -> testable, cheap every cycle.
"""

from __future__ import annotations

from typing import Any

_ACTIONABLE = ("execution_issue", "infrastructure_bug")   # + persistent alpha_decay via governance


def classify(ev: dict[str, Any]) -> dict[str, Any]:
    """Classify one period's realized deviation. ``ev`` carries cheap observable evidence:

    net_pnl / expected_pnl ($, the period), funding_earned, fees_paid, orphan_or_drift_events (n),
    restarts (n), maker_share (0..1 or None), fwd_sharpe / bt_sharpe (edge health),
    assumption_breaks (n, e.g. fee-schedule or funding-timestamp changes detected).
    Returns confidence per bucket (sums to 1), the top cause, and the allowed action.
    """
    net = float(ev.get("net_pnl", 0.0))
    exp = float(ev.get("expected_pnl", 0.0))
    dev = net - exp                                        # tracking error in $
    drift = int(ev.get("orphan_or_drift_events", 0))
    restarts = int(ev.get("restarts", 0))
    maker = ev.get("maker_share")
    fees = abs(float(ev.get("fees_paid", 0.0)))
    funding = float(ev.get("funding_earned", 0.0))
    fwd, bt = ev.get("fwd_sharpe"), ev.get("bt_sharpe")
    breaks = int(ev.get("assumption_breaks", 0))

    w = dict.fromkeys(("expected_variance", "execution_issue", "infrastructure_bug",
                       "model_assumption", "alpha_decay", "regime_shift"), 0.05)
    # deviation small relative to the funding scale -> expected variance dominates
    scale = max(abs(exp), funding, 5.0)
    if abs(dev) <= 2.0 * scale:
        w["expected_variance"] += 2.0
    # hedge drift / orphans / restarts are INFRASTRUCTURE, the desk's dominant realized loss so far
    if drift > 0 or restarts > 1:
        w["infrastructure_bug"] += 1.5 * min(drift + max(restarts - 1, 0), 4)
    # fees swamping funding, or maker share collapsed -> execution
    if fees > max(funding, 1e-9) or (maker is not None and float(maker) < 0.3):
        w["execution_issue"] += 1.2
    # forward edge statistically deteriorating vs backtest -> decay (needs persistence to act)
    if fwd is not None and bt is not None and float(bt) > 0 and float(fwd) < 0.25 * float(bt):
        w["alpha_decay"] += 1.0
    if breaks > 0:
        w["model_assumption"] += 2.0 * breaks
    tot = sum(w.values())
    conf = {k: round(v / tot, 3) for k, v in w.items()}
    top = max(conf, key=lambda k: conf[k])
    # UNKNOWN/NOVEL (2026-07-12 external review): the six buckets are KNOWN failure modes,
    # but the world's failure modes are open. A large deviation that matches NO evidence
    # pattern (flat confidence) is the most dangerous case -- classifying it into the
    # least-bad known bucket would trigger the wrong playbook. Verdict: pause new risk
    # and page the principal; never force-fit a novel event into a familiar box.
    # MATERIALITY GATE (round-2 review: paging on immaterial ambiguity = pager fatigue,
    # and a numb principal is a dead control): unknown_novel requires the deviation to be
    # real money -- > max($25, 0.3% of NAV when ``nav`` is supplied). Immaterial ambiguity
    # stays monitor_only; a large ambiguous loss still pages.
    material = abs(dev) > max(25.0, 0.003 * float(ev.get("nav", 0.0) or 0.0))
    if conf[top] < 0.35 and material:
        return {"confidence": conf, "top_cause": "unknown_novel", "top_confidence": conf[top],
                "action": "pause_and_page", "tracking_error_usd": round(dev, 2),
                "rule": "never modify strategy parameters from realized PnL alone"}
    action = ("act_autonomously" if top in _ACTIONABLE and conf[top] >= 0.5
              else "freeze_and_audit" if top == "model_assumption" and conf[top] >= 0.5
              else "monitor_only")
    return {"confidence": conf, "top_cause": top, "top_confidence": conf[top],
            "action": action, "tracking_error_usd": round(dev, 2),
            "rule": "never modify strategy parameters from realized PnL alone"}


def implementation_shortfall(expected_bps: float, fees_bps: float,
                             realized_bps: float) -> dict[str, float]:
    """Expected edge -> after-fees -> realized: attribute the missing bps so 'where did it go?'
    has a number (fees vs everything-else = slippage/missed fills/timing/sizing)."""
    after_fees = expected_bps - fees_bps
    missing = after_fees - realized_bps
    return {"expected_bps": round(expected_bps, 2), "after_fees_bps": round(after_fees, 2),
            "realized_bps": round(realized_bps, 2), "missing_bps": round(missing, 2),
            "fees_share_bps": round(fees_bps, 2)}
