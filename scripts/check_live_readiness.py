#!/usr/bin/env python3
"""LIVE READINESS -- one gate, decided by evidence, that says what size is currently earned.

WHY THIS EXISTS AS A SINGLE FILE (principal 2026-08-26, item 10). "Are we ready to trade live"
was previously answerable only by reading eight artifacts and forming an impression, which is how
a desk talks itself into sizing. This computes it, publishes the reasons, and refuses to produce
a number when the inputs are unmeasured.

THE LADDER. Each rung requires the one below it, and nothing skips:

  0  NOT_READY        any hard requirement unmet
  1  PROBATIONARY     a sleeve has cleared forward evidence AND execution is measured AND it adds
                      an independent bet -- tiny size, single sleeve, capped
  2  SCALING          probationary sleeves have produced NET LIVE results consistent with their
                      shadow expectancy, and calibration has stayed stable
  3  FULL             sustained live agreement across several independent bets

WHY IT REFUSES TO NAME A CAGR. A growth target is a claim about a distribution nobody has
sampled. Until forward observations exist, any CAGR figure is the backtest's number wearing a
forward label -- and the backtest is the thing under suspicion. The gate reports what evidence
would be needed to earn a target, not the target.

HARD REQUIREMENTS, each one a thing that has actually failed on this desk:

  chronology   every live clock's evidence must postdate its own frozen start (it did not: n=7
               forward observations dated eight days before the clock)
  identity     no clock may be running with drifted code/params/costs (registry verifies)
  execution    slippage and fills measured recently on the venue's own tape (32% of decisions
               never filled; median slippage 0.297R on a 0.13R edge)
  independence N_eff must exceed 1 -- fifteen variants of one bet is one bet
  freshness    no STALE or FROZEN artifact in the job manifest (the tape died hourly, silently)
  decay        the live decay monitor must be armed and current
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "live_readiness.json"

#: A probationary sleeve may risk this fraction of equity per trade -- deliberately tiny, because
#: its purpose is to BUY EVIDENCE about live fills, not returns.
PROBATION_RISK_FRAC = 0.0025
MIN_FORWARD_TRADES = 20
MIN_FORWARD_DAYS = 14


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _age_h(stamp) -> float | None:
    try:
        t = datetime.fromisoformat(str(stamp))
        t = t.replace(tzinfo=UTC) if t.tzinfo is None else t
        return (datetime.now(tz=UTC) - t).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def main() -> int:
    now = datetime.now(tz=UTC)
    reasons: list[str] = []
    checks: dict[str, dict] = {}

    # --- chronology ------------------------------------------------------------------------
    shadow = _read(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    live_rows = {k: v for k, v in shadow.items()
                 if isinstance(v, dict) and "status" in v
                 and not str(v.get("status") or "").upper().startswith(
                     ("RETIRED", "KILL", "DEAD", "REJECT", "QUARANTIN", "PROMOTED", "IDENTITY"))}
    unstamped = [k for k, v in live_rows.items() if not v.get("forward_start")]
    contaminated = [k for k, v in live_rows.items()
                    if v.get("first_entry") and v.get("forward_start")
                    and str(v["first_entry"]) < str(v["forward_start"])[:10]]
    ok = not unstamped and not contaminated
    checks["chronology"] = {"pass": ok, "clocks": len(live_rows),
                            "unstamped": len(unstamped), "contaminated": len(contaminated)}
    if not ok:
        reasons.append(f"chronology: {len(unstamped)} clock(s) unstamped, {len(contaminated)} "
                       f"carrying evidence older than their own start")

    # --- identity --------------------------------------------------------------------------
    reg = _read(DESK / "data" / "sleeve_registry.json") or {}
    rows = reg.get("sleeves") or {}
    broken = [k for k, v in rows.items()
              if str(v.get("status") or "").upper() == "IDENTITY_BROKEN"]
    checks["identity"] = {"pass": not broken and bool(rows), "registered": len(rows),
                          "broken": len(broken)}
    if broken:
        reasons.append(f"identity: {len(broken)} sleeve(s) drifted after freezing")
    elif not rows:
        reasons.append("identity: registry is EMPTY -- no sleeve has a frozen identity, so "
                       "nothing can be shown to be the thing that was certified")

    # --- execution -------------------------------------------------------------------------
    try:
        sys.path.insert(0, str(DESK))
        from mt5desk.shadow_execution import is_stale
        stale, why = is_stale(DESK / "reports" / "execution_quality.json")
    except Exception as exc:
        stale, why = True, f"execution module unavailable: {exc}"
    checks["execution"] = {"pass": not stale, "why": why}
    if stale:
        reasons.append(f"execution: {why}")

    # --- independence ----------------------------------------------------------------------
    port = _read(DESK / "reports" / "portfolio_evidence.json") or {}
    n_eff = ((port.get("effective_bets") or {}).get("n_effective"))
    ok = isinstance(n_eff, (int, float)) and n_eff > 1.0
    checks["independence"] = {"pass": ok, "n_effective": n_eff}
    if not ok:
        reasons.append(f"independence: N_eff={n_eff} -- the book is one bet however many names "
                       f"it holds; sizing several correlated variants as separate sleeves takes "
                       f"more risk than the diversification earns")

    # --- freshness -------------------------------------------------------------------------
    man = _read(ROOT / "data" / "job_manifest.json") or {}
    summary = man.get("summary") or {}
    bad = sum(v for k, v in summary.items() if k in ("STALE", "FROZEN", "MISSING"))
    checks["freshness"] = {"pass": bad == 0 and bool(summary), "summary": summary}
    if bad:
        reasons.append(f"freshness: {bad} artifact(s) STALE/FROZEN/MISSING -- an organ is failing "
                       f"without saying so")

    # --- decay -----------------------------------------------------------------------------
    decay = _read(DESK / "data" / "decay_live.json") or {}
    age = _age_h(decay.get("checked_at"))
    ok = age is not None and age < 26
    checks["decay"] = {"pass": ok, "age_h": None if age is None else round(age, 2)}
    if not ok:
        reasons.append("decay: the live decay monitor has not run recently -- nothing would "
                       "demote a sleeve that stops working")

    # --- forward evidence, the thing that actually earns a rung -----------------------------
    eligible = [k for k, v in live_rows.items()
                if int(v.get("n") or 0) >= MIN_FORWARD_TRADES
                and int(v.get("days_active") or 0) >= MIN_FORWARD_DAYS
                and float(v.get("exp_r") or 0) > 0.05]
    checks["forward_evidence"] = {"pass": bool(eligible), "eligible_sleeves": eligible,
                                  "requires": f"n>={MIN_FORWARD_TRADES} and "
                                              f"days>={MIN_FORWARD_DAYS} and exp>0.05R"}
    if not eligible:
        soonest = max((int(v.get("days_active") or 0) for v in live_rows.values()), default=0)
        reasons.append(f"forward evidence: no sleeve has cleared the forward window "
                       f"(best clock is day {soonest}/{MIN_FORWARD_DAYS}); the market has not yet "
                       f"supplied the unseen observations, and nothing can substitute for them")

    hard_pass = all(c.get("pass") for c in checks.values())
    if hard_pass:
        rung, label = 1, "PROBATIONARY"
    else:
        rung, label = 0, "NOT_READY"

    report = {
        "assessed_at": now.isoformat(timespec="seconds"),
        "rung": rung, "status": label,
        "probation_risk_frac": PROBATION_RISK_FRAC if rung >= 1 else 0.0,
        "checks": checks,
        "blocking": reasons,
        "cagr_target": None,
        "cagr_note": ("Deliberately null. A growth target is a claim about a distribution nobody "
                      "has sampled; until forward observations exist, any figure would be the "
                      "backtest's number wearing a forward label -- and the backtest is the thing "
                      "under suspicion."),
        "what_would_earn_the_next_rung": (
            "one certified sleeve completing 14 days and 20+ FORWARD trades at >0.05R, on a book "
            "whose N_eff exceeds 1, with execution measured inside 36h" if rung == 0 else
            "net LIVE results consistent with the shadow expectancy, at probationary size, with "
            "calibration stable across the window"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    print(f"live readiness: rung {rung} ({label}); "
          f"{sum(1 for c in checks.values() if c.get('pass'))}/{len(checks)} checks pass")
    for r in reasons:
        print(f"   BLOCKING  {r}")
    return 0 if rung >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
