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
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.ops.fresh import read_fresh
from libs.ops.lawful import guard

_OUT = Path("web/growth_audit.json")
_UTIL_TARGET = 0.75          # deployed/(deployed+idle spot USDT) below this -> investigate
_KILL = Path("data/CASHCARRY_KILL")
#: The forward clock is produced by the daily research chain (run_daily_research.py step
#: "cash-and-carry forward shadow"), so one day plus slack is the honest tolerance. Measured
#: 2026-08-20: the artifact was 65h old and this check read it with no contract at all.
_SHADOW_MAX_AGE_H = 36.0


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


def _rail_override(justified: str, clamp: dict[str, str] | None, action: str) -> str:
    """R0274 GENERALISED: no check may call this desk timid for not doing something a latched
    survival rail forbids.

    R0274 fixed exactly this for check #1 and the fix was never carried to its siblings, so the
    class came back on new input -- which is the defect the carry-over brief names: a per-instance
    fix buys one cycle, the rule has to be generalised or it returns. Measured 2026-08-20: check #4
    published `NONE -- eligible sleeve not promoted = pure foregone growth` about the cash-and-carry
    sleeve whose executor carries `_PERMANENTLY_RETIRED = True` (run_cashcarry_executor.py:64,
    principal order 2026-08-19) on a universe the MT5 mandate permanently closed. `justified_by`
    starting with NONE is what `conservatism_defects` is derived from and therefore what an organ
    ACTS on, and this artifact's own rule tells that organ to "close it same-cycle" -- so the audit
    was standing instruction to promote a killed sleeve toward capital. That is the dangerous
    direction of the two (L1.23: rails are the floor aggression stands on, never a defect).

    THE GAP STILL READS AS A GAP. Only the JUSTIFICATION changes -- naming the rail must never
    launder under-deployment into health (the denominator trick pointed at verdicts).
    """
    if clamp is None or not justified.startswith("NONE"):
        return justified
    return (f"RAIL ({clamp['rail']}) -- {clamp['detail']}. NOT a conservatism defect: {action} "
            f"cannot proceed while the book is held flat by a fired survival rail, and re-arming "
            f"is a principal decision. Lifting condition: {clamp['lifting_condition']}")



def _permanently_retired() -> bool:
    """Is the cash-and-carry sleeve retired FOREVER, or merely held by a latched rail?

    THE TWO ARE NOT THE SAME VERDICT, and conflating them was the whole argument between the two
    fixes this file carries. R0274-generalised (2026-08-20) holds that naming a rail may change a
    justification but NEVER a verdict, because a verdict change launders under-deployment into
    health -- correct for a TEMPORARY clamp, which lifts and leaves a real gap behind it. The
    2026-08-27 fix holds that "ACT-NOW: promote this sleeve" is a standing instruction to move a
    dead book toward capital -- correct for a sleeve the principal retired PERMANENTLY (b0fe6f50)
    on a universe the MT5 mandate closed for good, where no lifting condition exists at all.

    So permanence is the discriminator, and it is read from the executor's own declaration rather
    than inferred from the rail file: a rail can be latched on a perfectly live book, and that
    book's gap must keep reading as a gap.

    Read as TEXT, not imported: importing the executor pulls venue clients and module-scope state
    into an audit that must stay a pure read. A parse failure returns False -- the answer that
    keeps the anti-timidity gate LOUD, never the one that quietly excuses under-deployment.
    """
    try:
        src = Path("scripts/run_cashcarry_executor.py").read_text("utf-8")
    except OSError:
        return False
    return re.search(r"^_PERMANENTLY_RETIRED\s*=\s*True\b", src, re.M) is not None

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
    guard()  # L1.42: no entry point is exempt from the laws.
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
    item: dict[str, Any] = {
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
    items.append({
        "check": "leverage_vs_growth_optimal",
        "utilized": f"{actual_lev:g}x", "authorized": f"recommended {rec:g}x @ conf {conf:g} "
        f"(ruin cap {_num(sl.get('ruin_cap')):g}x)",
        "verdict": "GAP" if lev_gap else "OK",
        # Same latent defect as #4, dormant only because confidence is currently 0: the moment
        # confidence goes positive on a rail-clamped book this would demand the auto-ramp engage
        # on a flat book. Clamped at source rather than left to fire later.
        "justified_by": _rail_override(
            ("NONE -- validation confidence is positive but sizing has not ramped: "
             "the auto-ramp MUST engage (this is the defect class the audit exists for)"
             if lev_gap else
             "evidence (confidence=0: floored on unproven edge is honest, not timid)"),
            clamp, "ramping size"),
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
    # L1.44 CONSUMPTION-TIME FRESHNESS. This read had NO contract, and on 2026-08-20 the artifact
    # was 65h stale: it still carried `fast_track = ELIGIBLE ...` from forward day 52, so this
    # check published ACT-NOW / "pure foregone growth". Re-running the producer took seconds and
    # the verdict INVERTED -- day 55, `regime evidence PENDING (events 0, funding-vol 5e-05 vs bar
    # 7e-05)`: the window sits in the calmest quartile, which is the one thing REGIME EVIDENCE v2
    # exists to refuse. The desk's only published conservatism defect was an artifact of a stale
    # input, in the direction that urges capital forward. A stale clock cannot license a promotion
    # claim in EITHER direction, so staleness resolves to UNMEASURED and never to ACT-NOW
    # (L1.28a: absence must never resolve to a clean verdict -- still less to an actionable one).
    fr = read_fresh("web/cashcarry_shadow.json", max_age_h=_SHADOW_MAX_AGE_H,
                    caller="run_growth_audit.promotion_latency")
    sh = fr.data if isinstance(fr.data, dict) else {}
    ft = str(sh.get("fast_track", ""))
    if not fr.fresh:
        p_verdict = "UNMEASURED"
        p_just = (f"UNMEASURED -- the forward clock's own artifact is not fresh ({fr.why}). "
                  "A stale clock cannot license a promotion claim in either direction; re-run "
                  "scripts/run_cashcarry_shadow.py (it is a daily-research-chain step) before "
                  "reading this check.")
        p_used = f"STALE READ REFUSED (age {fr.age_h if fr.age_h is None else round(fr.age_h, 1)}h)"
    elif ft.startswith("ELIGIBLE") and clamp is not None and _permanently_retired():
        # ...AND THE SLEEVE IS RETIRED FOREVER -- both conditions, never the rail alone. Kept
        # from the 08-27 fix rather than dropped as the cost of restoring the older
        # generalisation, and narrowed by _permanently_retired() so the two designs stop
        # contradicting each other: a merely-clamped book keeps its ACT-NOW (the clamp lifts and
        # the gap is real), while a book the principal retired for good gets a verdict a reader
        # can act on. _rail_override below rewrites a NONE justification but cannot touch a
        # VERDICT, and "ACT-NOW" is the field an organ acts on.
        p_verdict = "RETIRED"
        p_just = (f"RAIL ({clamp['rail']}) -- {clamp['detail']}; latched {clamp['since']}. The "
                  f"sleeve is retired, so its eligibility is arithmetic about a book that will "
                  f"never take another fill, NOT foregone growth. Lifting condition: the same "
                  f"principal re-arm item 1 names -- re-arming a rail is never autonomous.")
        p_used = ft
    elif ft.startswith("ELIGIBLE"):
        p_verdict = "ACT-NOW"
        p_just = "NONE -- eligible sleeve not promoted = pure foregone growth"
        p_used = ft
    else:
        p_verdict, p_just, p_used = "OK", "evidence clock", ft or "n/a"
    items.append({
        "check": "promotion_latency",
        "utilized": p_used, "authorized": "promote the DAY eligibility hits (40d + t>=1.65)",
        "verdict": p_verdict,
        "justified_by": _rail_override(p_just, clamp, "promotion of this sleeve"),
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
