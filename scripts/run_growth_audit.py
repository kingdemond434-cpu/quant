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
_KILL = Path("data/CASHCARRY_KILL")


def _clamp_state() -> dict[str, str] | None:
    """The rail holding the book flat, if one is latched -- otherwise None.

    Returns None when nothing explains the under-deployment, which is exactly when the gap IS a
    conservatism defect and must keep saying so. An unreadable kill file returns a clamp with the
    read error as its detail rather than None: "I could not tell" and "no rail is latched" are
    different claims and only one of them licenses calling the desk timid (L1.55).
    """
    if not _KILL.exists():
        return None
    try:
        detail = _KILL.read_text("utf-8").strip() or "(kill file present but empty)"
    except OSError as e:
        detail = f"kill file present but UNREADABLE ({e}) -- treat as latched"
    try:
        since = datetime.fromtimestamp(_KILL.stat().st_mtime, tz=UTC).isoformat()
    except OSError:
        since = "unknown"
    # L1.51 pricing. `mode` on this book is live-paper, so a dollar figure would be computed from
    # a simulated denominator -- the law is explicit that publishing one is WORSE than publishing
    # none, because a reader acts on it. The refusal IS the measurement here.
    return {"rail": "CASHCARRY_KILL", "detail": detail, "since": since,
            "holds_usd": "UNMEASURABLE-PAPER-BOOK",
            "usd_per_day": "UNMEASURABLE-PAPER-BOOK",
            "cumulative_usd": "UNMEASURABLE-PAPER-BOOK",
            "price_note": ("the desk has never deployed live capital, so the cost of this clamp "
                           "has no honest denominator; that statement is louder than any number"),
            "lifting_condition": ("principal re-arm (Tier-3 adjacent: removing/disabling a rail "
                                  "is never autonomous). On re-arm, RESTART the executor and "
                                  "verify the new behaviour appears in web/cashcarry_live.json "
                                  "-- a committed fix is inert until the process restarts")}


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
    # R0274: THE AUDIT COULD NOT TELL TIMIDITY FROM A LATCHED KILL SWITCH, and that is the more
    # dangerous direction of the two. `justified_by` was hardcoded to "NONE -- ..." for ANY
    # under-deployment, so a book held flat by a fired ruin rail was published as a CONSERVATISM
    # DEFECT -- and the rule this same artifact carries tells its reader to "close it same-cycle".
    # An organ obeying that against a latched rail closes it by RE-ARMING A KILLED BOOK. The audit
    # exists to attack unjustified caution; it must never mistake a survival rail for caution
    # (L1.23: the rails are the floor aggression stands on, never a defect).
    #
    # THE GAP STILL READS "GAP". Naming the rail does not turn under-deployment into health --
    # that would be the denominator trick pointed at verdicts. What changes is the JUSTIFICATION,
    # which is what `conservatism_defects` is derived from and therefore what an organ acts on.
    clamp = _clamp_state()
    if util is not None and util >= _UTIL_TARGET:
        justified = "fully deployed to the authorized ceiling"
    elif clamp:
        justified = (f"RAIL ({clamp['rail']}) -- {clamp['detail']}. NOT a conservatism defect: "
                     f"the book is held flat by a fired survival rail, and re-arming is a "
                     f"principal decision. Lifting condition: {clamp['lifting_condition']}")
    else:
        justified = ("NONE -- authorized capital is not fully deployed: the executor "
                     "should be using its full config capital (check free-capital sizing "
                     "/ open blocks)")
    item = {
        "check": "carry_capital_utilization",
        "utilized": f"${dep:,.0f} deployed", "authorized": f"${authorized:,.0f} authorized "
        f"(config) | wallet idle ${idle:,.0f} (info: raising authorized capital is a "
        "principal decision)",
        "utilization": util,
        "verdict": ("OK" if util is None or util >= _UTIL_TARGET else "GAP"),
        "justified_by": justified,
    }
    if clamp:
        # L1.51: every clamp carries its price and its lifting condition, or it is UNPRICED.
        # On a paper/simulated book the price is deliberately NOT a number: "a cost from a
        # simulated denominator is WORSE than no number because a reader will act on it".
        item["clamp"] = clamp
    items.append(item)

    # 2) LEVERAGE vs the growth-optimal target: floored is OK ONLY while confidence == 0.
    sl = lv.get("sleeves", {}).get("cash_and_carry", {})
    conf = _num(sl.get("confidence"))
    rec = _num(sl.get("recommended_leverage"))
    actual_lev = 1.0
    lev_gap = conf > 0 and rec > actual_lev * 1.1
    # THE SAME RETIRED-BOOK BLINDNESS AS ITEM 4, ONE ROW UP (found 2026-08-28). Item 4 was taught
    # to consult `_clamp_state()` on 2026-08-27; this item reads the SAME `cash_and_carry` sleeve
    # and was left shouting `NONE -- the auto-ramp MUST engage` about a book the principal
    # permanently retired (b0fe6f50), held flat by a latched rail, whose entire universe the MT5
    # mandate forbids trading ever again. Fixing item 4 alone bought one cycle: this is the
    # per-instance repair the carry-over law calls the defect, so the clamp is now consulted
    # wherever an item is scoped to a clamped book rather than in the one row somebody noticed.
    #
    # NOT A SOFTENING, and the direction is the whole argument. Ramping leverage on a book that
    # cannot take a fill is not growth foregone, it is arithmetic; and an anti-timidity gate that
    # spends its authority on retired ground is how a REAL under-deployment gets read as noise.
    # The gate stays exactly as strict on a live book: only a LATCHED RAIL moves the verdict, and
    # the justification names the rail instead of pretending the ramp is running.
    if lev_gap and clamp is not None:
        lev_verdict = "RETIRED"
        lev_why = (f"RAIL ({clamp['rail']}) -- {clamp['detail']}; latched {clamp['since']}. The "
                   f"sleeve is retired, so a {rec:g}x recommendation is arithmetic about a book "
                   f"that will never take another fill, NOT foregone growth. Lifting condition: "
                   f"the same principal re-arm item 1 names -- re-arming a rail is never "
                   f"autonomous, and on re-arm this row becomes a live ACT-NOW again.")
    elif lev_gap:
        lev_verdict = "GAP"
        lev_why = ("NONE -- validation confidence is positive but sizing has not ramped: "
                   "the auto-ramp MUST engage (this is the defect class the audit exists for)")
    else:
        lev_verdict = "OK"
        lev_why = "evidence (confidence=0: floored on unproven edge is honest, not timid)"
    items.append({
        "check": "leverage_vs_growth_optimal",
        "utilized": f"{actual_lev:g}x", "authorized": f"recommended {rec:g}x @ conf {conf:g} "
        f"(ruin cap {_num(sl.get('ruin_cap')):g}x)",
        "verdict": lev_verdict,
        "justified_by": lev_why,
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
    #
    # ...UNLESS THE SLEEVE IS RETIRED. This item reads the cash-carry shadow, and item 1 above
    # already consults `_clamp_state()` for the SAME book -- but this one never did, so it kept
    # publishing `ACT-NOW / justified_by: NONE -- pure foregone growth` for a strategy that the
    # principal PERMANENTLY RETIRED on real capital (b0fe6f50) and whose entire universe the
    # standing MT5 mandate forbids trading or hunting ever again (LAWS section 1). Measured
    # 2026-08-27: data/CASHCARRY_KILL latched since 2026-08-15T20:55, and
    # web/cashcarry_shadow.json still rewritten that morning with `fast_track: ELIGIBLE ... ->
    # live-promotable`, forward_days 62, forward_tstat 2.85.
    #
    # This is NOT softening the anti-timidity gate, and the direction matters. A safety gate that
    # goes stale fails CLOSED and someone notices. An anti-timidity gate that goes stale fails by
    # SHOUTING -- it agrees with desk doctrine, so nobody discounts it -- and this one was
    # shouting "promote to live capital" at a banned universe every cycle. A gate that spends its
    # authority on retired ground is how a real ACT-NOW gets read as noise. The check stays
    # exactly as strict wherever a live sleeve is genuinely eligible: only a LATCHED RAIL moves
    # the verdict, and the justification names the rail rather than claiming the clock is running.
    sh = _load("web/cashcarry_shadow.json")
    ft = str(sh.get("fast_track", ""))
    eligible = ft.startswith("ELIGIBLE")
    if eligible and clamp is not None:
        verdict = "RETIRED"
        why = (f"RAIL ({clamp['rail']}) -- {clamp['detail']}; latched {clamp['since']}. The "
               f"sleeve is retired, so its eligibility is arithmetic about a book that will "
               f"never take another fill, NOT foregone growth. Lifting condition: the same "
               f"principal re-arm item 1 names -- re-arming a rail is never autonomous.")
    elif eligible:
        verdict, why = "ACT-NOW", "NONE -- eligible sleeve not promoted = pure foregone growth"
    else:
        verdict, why = "OK", "evidence clock"
    items.append({
        "check": "promotion_latency",
        "utilized": ft or "n/a", "authorized": "promote the DAY eligibility hits (40d + t>=1.65)",
        "verdict": verdict,
        "justified_by": why,
    })

    defects = [i["check"] for i in items if str(i["justified_by"]).startswith("NONE")]
    out = {"updated": datetime.now(tz=UTC).isoformat(), "items": items,
           "conservatism_defects": defects,
           "rule": ("every NONE-gap is a DEFECT: close it same-cycle or ledger-justify it. "
                    "Floors are for missing evidence, never for comfort. Conservatism beyond "
                    "survival constraints is a cost to lifetime geometric growth.")}
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    # THE SUMMARY LINE MUST NOT SAY "fully deployed" ABOUT A RAIL-CLAMPED BOOK. Zero conservatism
    # defects and full deployment are different states, and after R0274 they came apart: a killed
    # book has no conservatism defect and is not deployed at all. Collapsing them would hand the
    # reader the same false all-clear the justification field just stopped giving.
    clamped = [i["check"] for i in items if i.get("clamp")]
    if defects:
        tail = f" -> {defects}"
    elif clamped:
        tail = (f" -- none are timidity, but {clamped} sit(s) under a latched rail and are NOT "
                f"deployed; see .clamp for the lifting condition")
    else:
        tail = " -- fully deployed to authorized ceilings"
    print(f"growth audit: {len(defects)} conservatism defect(s)" + tail)


if __name__ == "__main__":
    main()
