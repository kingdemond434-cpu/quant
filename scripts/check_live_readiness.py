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

from libs.ops.forward_clock import forward_days, overstated_rows, served_window

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


def project_eligibility(live_rows: dict[str, dict[str, object]],
                        now: datetime) -> list[dict[str, object]]:
    """Per-clock distance to BOTH halves of the forward gate, and the day it clears them.

    Eligibility needs ``n >= MIN_FORWARD_TRADES`` AND ``days >= MIN_FORWARD_DAYS``. Until
    2026-08-29 only the DAYS half was published, so the desk read "day 2/14" and understood
    twelve days to go while the observation count was the half that actually bound. Measured the
    day this shipped: 17 active clocks at almost exactly 1.00 observation per clock-day (a
    session-scoped sleeve gets one session a day), so a clock holds n=14 on the day it reaches
    day 14 and the count binds for about another week.

    ``eligible_day`` is ``None`` where the rate cannot be measured -- a clock with no elapsed
    time or no observations has no evidenced arrival date, and projecting an optimistic one from
    nothing is exactly the failure this function exists to end (L1.28a). It never reports a day
    earlier than ``MIN_FORWARD_DAYS``: satisfying one half early does not satisfy the other.

    Reporting only. No threshold here is this organ's to move (LAWS s4).
    """
    rows: list[dict[str, object]] = []
    for key, v in live_rows.items():
        days, n = forward_days(v, now) or 0, int(v.get("n") or 0)
        rate = (n / days) if days > 0 and n > 0 else None
        day_n = None if rate is None else days + max(0.0, (MIN_FORWARD_TRADES - n) / rate)
        rows.append({"clock": key, "days": days, "n": n,
                     "rate_per_day": None if rate is None else round(rate, 2),
                     "eligible_day": None if day_n is None
                     else round(max(float(MIN_FORWARD_DAYS), day_n), 1)})
    return rows


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
    # A STORED DAY COUNT IS NOT EVIDENCE OF ELAPSED TIME. `days_active` used to be computed from
    # the first trade the sleeve ever took; rows written before that was corrected still carry the
    # old number, and it outran the pre-registration stamp by up to eight days (measured
    # 2026-08-27: 31 of 47 rows). Every gate below DERIVES the window from `forward_start`, and a
    # row whose stored count cannot be accounted for by its own stamp is a chronology failure --
    # not a display quirk, because the promote lanes read that field.
    overstated = overstated_rows(live_rows, now)
    ok = not unstamped and not contaminated and not overstated
    checks["chronology"] = {"pass": ok, "clocks": len(live_rows),
                            "unstamped": len(unstamped), "contaminated": len(contaminated),
                            "overstated_day_counts": len(overstated),
                            "worst_overstatement_days": max(
                                (v["overstated_by"] for v in overstated.values()), default=0)}
    if not ok:
        reasons.append(f"chronology: {len(unstamped)} clock(s) unstamped, {len(contaminated)} "
                       f"carrying evidence older than their own start, {len(overstated)} whose "
                       f"stored day count outruns their own pre-registration stamp")

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
    bets = port.get("effective_bets") or {}
    n_eff = bets.get("n_effective")
    n_sleeves = bets.get("n_sleeves") or 0
    ok = isinstance(n_eff, (int, float)) and n_eff > 1.0
    # UNMEASURED IS NOT "FULLY CORRELATED". N_eff comes out 0 in two completely different worlds:
    # a book whose sleeves all move together, and a book with no forward observations to
    # correlate at all. This check reported both as "the book is one bet however many names it
    # holds" -- a verdict about correlation drawn from an absence of data, which is precisely the
    # error L1.28a names and which this desk has been bitten by repeatedly. They need different
    # answers because they need different ACTIONS: one is fixed by holding different mechanisms,
    # the other only by elapsed time.
    measured = int(n_sleeves) >= 2
    checks["independence"] = {"pass": ok, "n_effective": n_eff, "n_sleeves": n_sleeves,
                              "measured": measured}
    if not ok and not measured:
        reasons.append(f"independence: UNMEASURED -- only {n_sleeves} sleeve(s) have forward "
                       f"observations, so there is nothing to correlate yet. This is not a "
                       f"finding that the book is concentrated; it is the absence of a book to "
                       f"measure, and only elapsed forward time resolves it.")
    elif not ok:
        reasons.append(f"independence: N_eff={n_eff} across {n_sleeves} sleeve(s) -- the book is "
                       f"one bet however many names it holds; sizing correlated variants as "
                       f"separate sleeves takes more risk than the diversification earns. Fixed "
                       f"by certifying a different MECHANISM, not by waiting.")

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
    # DERIVED, never restated: `served_window` measures from `forward_start` and fails closed on
    # an unstamped row, so no sleeve can clear a window it did not serve (LAWS L1.58).
    eligible = [k for k, v in live_rows.items()
                if int(v.get("n") or 0) >= MIN_FORWARD_TRADES
                and served_window(v, MIN_FORWARD_DAYS, now)
                and float(v.get("exp_r") or 0) > 0.05]
    # BOTH HALVES OF THE GATE, AND THE BINDING ONE NAMED (2026-08-29). Eligibility has always
    # required n>=MIN_FORWARD_TRADES *and* days>=MIN_FORWARD_DAYS, but the published progress
    # tracked DAYS alone -- so the desk read "day 2/14" and understood "twelve days to go" while
    # the actually-binding half went unreported. Measured on this box the day it was fixed: all
    # 17 active clocks accrue almost exactly 1.00 observation per clock-day, because a
    # session-scoped sleeve gets one session a day. At that rate a clock holds n=14 when it
    # reaches day 14 and the observation count binds for roughly another week. A two-part gate
    # reported by its non-binding part is a progress bar pointing at the wrong wall.
    #
    # NOTHING HERE CHANGES A THRESHOLD. The bars are untouched and are not this organ's to move
    # (LAWS s4); only what the desk is told about its distance from them changes.
    eta_rows = project_eligibility(live_rows, now)
    etas = [float(r["eligible_day"]) for r in eta_rows if r["eligible_day"] is not None]
    checks["forward_evidence"] = {"pass": bool(eligible), "eligible_sleeves": eligible,
                                  "requires": f"n>={MIN_FORWARD_TRADES} and "
                                              f"days>={MIN_FORWARD_DAYS} and exp>0.05R",
                                  "clocks": eta_rows,
                                  "soonest_eligible_day": min(etas) if etas else None}
    if not eligible:
        soonest = max((forward_days(v, now) or 0 for v in live_rows.values()), default=0)
        best_n = max((int(v.get("n") or 0) for v in live_rows.values()), default=0)
        rates = [float(r["rate_per_day"]) for r in eta_rows if r["rate_per_day"] is not None]
        rate_txt = (f"{sum(rates) / len(rates):.2f} obs/clock-day measured" if rates
                    else "observation rate UNMEASURED")
        eta = min(etas) if etas else None
        binding = ("OBSERVATIONS" if eta is not None and eta > MIN_FORWARD_DAYS
                   else "TIME" if eta is not None else "UNMEASURED")
        eta_txt = (f"earliest eligibility ~day {eta:.0f} at the current rate"
                   if eta is not None else
                   "no clock has produced enough to project an arrival day")
        reasons.append(f"forward evidence: no sleeve has cleared the forward window "
                       f"(best clock is day {soonest}/{MIN_FORWARD_DAYS} on TIME and "
                       f"{best_n}/{MIN_FORWARD_TRADES} on OBSERVATIONS; {rate_txt}; binding "
                       f"constraint is {binding}, {eta_txt}); the market has not yet supplied "
                       f"the unseen observations, and nothing can substitute for them")

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
