#!/usr/bin/env python3
"""P&L WATCHDOG -- every cycle, on every mode: live, testnet, shadow.

WHY IT RUNS ALWAYS AND NOT ON REQUEST. A loss that nobody looks at compounds in exactly the way
the objective says wealth compounds, only downward, and the desk's only P&L record is a
once-a-day NAV attestation that nothing reads. Between attestations a leak is invisible; across
them it is visible only if somebody opens the file. This makes "why are we down?" a question the
desk answers to itself every cycle rather than one a human has to think to ask.

WHAT IT CAN ANSWER, AND IT IS LESS THAN THE QUESTION DESERVES. The NAV chain gives equity, the
realized/marked split, deployed notional and leg count. From those it can say WHEN the desk lost
money, HOW MUCH, whether losses were BOOKED (realized fell) or marked, and whether the book
CONCENTRATED. Those are real findings and they are enough to raise an alarm.

WHAT IT CANNOT ANSWER, STATED LOUDLY RATHER THAN GUESSED. Attribution -- funding versus basis
versus slippage versus fees -- requires FILLS, and desk_metrics.fills is empty. So "is this a
leak or is this the market?" is not answerable from the data that exists, and this organ says so
instead of picking whichever story sounds most plausible. A confident attribution built from an
equity curve alone is a narrative, and a narrative gets acted on. The missing table is named in
the output so the gap is chased rather than tolerated.

NO AUTHORITY TO TRADE. This reports and alarms. It cannot flatten, resize or halt anything --
those paths belong to the risk rails, which are Tier-3 and never driven by an analysis organ.
"""
from __future__ import annotations

import itertools
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.portfolio_law import portfolio_entropy  # noqa: E402
from libs.ops.remediation import (  # noqa: E402
    AUTOFIX,
    BLOCKED,
    PATCH_READY,
    Leak,
    LeakLedger,
    apply_numeric_config_fix,
)

NAV = ROOT / "data/nav_attestation.jsonl"
METRICS = ROOT / "data/desk_metrics.sqlite"
OUT = ROOT / "data/pnl_watch.json"
LEAKS = ROOT / "data/pnl_leaks.json"
CONFIG = "data/cashcarry_config.json"

#: Cycles a leak may stand open before it stops being a finding and becomes a
#: DEFECT. "Escalated" is not a resting state -- a leak parked in it forever is an
#: excuse with a ticket number.
LEAK_STALE_CYCLES = 3

#: Single-day equity move, as a fraction, that is reported as an EVENT rather than as noise.
#: Deliberately low: the point is to notice early, and a false alarm costs one read of a JSON file
#: while a missed one costs the compounding the loss removed.
EVENT_MOVE = 0.02

#: Drawdown from the recorded peak that escalates the whole report.
DRAWDOWN_ALARM = 0.05

#: Fall in leg count, at roughly constant notional, that counts as the book CONCENTRATING. Same
#: money in fewer legs is more correlated risk wearing the same exposure number, and it is
#: invisible to any check that only watches notional.
CONCENTRATION_DROP = 0.4


def _rows() -> list[dict]:
    if not NAV.exists():
        return []
    out = []
    for line in NAV.read_text("utf-8", errors="ignore").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "equity_marked" in d:
            out.append(d)
    return sorted(out, key=lambda d: str(d.get("date", "")))


def _has_fills() -> bool:
    """Can P&L be ATTRIBUTED at all? Empty and absent are the same fact here."""
    if not METRICS.exists():
        return False
    try:
        import sqlite3
        with sqlite3.connect(f"file:{METRICS}?mode=ro", uri=True) as c:
            return bool(c.execute("select count(*) from fills").fetchone()[0])
    except Exception:
        return False


def analyse(rows: list[dict]) -> dict:
    """Everything the NAV chain supports, and nothing it does not."""
    if len(rows) < 2:
        return {"state": "INSUFFICIENT-HISTORY", "rows": len(rows),
                "note": "fewer than two attestations -- no move is computable, and inventing a "
                        "trend from one point is how a report becomes a story"}

    days, peak, dd_max = [], float(rows[0]["equity_marked"]), 0.0
    booked_loss_days, event_days, concentration = [], [], []
    for prev, cur in itertools.pairwise(rows):
        eq0, eq1 = float(prev["equity_marked"]), float(cur["equity_marked"])
        r0, r1 = float(prev.get("realized_spot_pnl", 0)), float(cur.get("realized_spot_pnl", 0))
        n0, n1 = int(prev.get("n_carries", 0)), int(cur.get("n_carries", 0))
        dep0, dep1 = float(prev.get("deployed_notional", 0)), float(cur.get("deployed_notional", 0))
        d_eq, d_real = eq1 - eq0, r1 - r0
        peak = max(peak, eq1)
        dd = (peak - eq1) / peak if peak > 0 else 0.0
        dd_max = max(dd_max, dd)
        row = {
            "date": str(cur.get("date", "")),
            "equity": round(eq1, 2),
            "d_equity": round(d_eq, 2),
            "d_realized": round(d_real, 2),
            # The marked (unrealized) move is what is LEFT after the booked change. Reported
            # because a day where realized rises and equity falls is unrealized loss crystallising
            # -- a completely different event from a day where both fall together.
            "d_marked": round(d_eq - d_real, 2),
            "drawdown_from_peak": round(dd, 4),
            "n_legs": n1,
            "deployed": round(dep1, 2),
        }
        days.append(row)
        if d_real < 0:
            booked_loss_days.append(row)
        if eq0 > 0 and abs(d_eq / eq0) >= EVENT_MOVE:
            event_days.append(row)
        if n0 > 0 and n1 < n0 * (1 - CONCENTRATION_DROP) and dep1 > dep0 * 0.6:
            concentration.append({**row, "n_legs_before": n0,
                                  "note": f"legs {n0} -> {n1} at {dep1 / max(dep0, 1e-9):.0%} of "
                                          "prior notional -- same money, fewer bets"})

    first, last = rows[0], rows[-1]
    total = float(last["equity_marked"]) - float(first["equity_marked"])
    ent = portfolio_entropy(dict.fromkeys(range(max(1, int(last.get("n_carries", 1)))), 1.0))
    return {
        "state": "MEASURED",
        "mode": str(last.get("mode", "unknown")),
        "from": str(first.get("date", "")), "to": str(last.get("date", "")),
        "equity_first": round(float(first["equity_marked"]), 2),
        "equity_last": round(float(last["equity_marked"]), 2),
        "total_pnl": round(total, 2),
        "total_pct": round(100.0 * total / max(1e-9, float(first["equity_marked"])), 2),
        "max_drawdown": round(dd_max, 4),
        "in_loss": total < 0,
        "days": days,
        "booked_loss_days": booked_loss_days,
        "event_days": event_days,
        "concentration_events": concentration,
        "effective_bets": ent["effective_bets"],
    }


def diagnose(a: dict, attributable: bool) -> dict:
    """What the evidence supports, and an explicit refusal where it does not."""
    if a.get("state") != "MEASURED":
        return {"verdict": a.get("state"), "findings": [], "blocked": []}

    findings, blocked = [], []
    if a["in_loss"]:
        findings.append(
            f"DOWN {a['total_pnl']:+.2f} ({a['total_pct']:+.2f}%) from {a['from']} to {a['to']} "
            f"in {a['mode']}; max drawdown {a['max_drawdown']:.1%} from peak.")
    if a["booked_loss_days"]:
        tot = sum(d["d_realized"] for d in a["booked_loss_days"])
        findings.append(
            f"{len(a['booked_loss_days'])} day(s) BOOKED realized losses totalling {tot:+.2f} -- "
            "cumulative realized P&L fell, which means legs were closed at a loss rather than "
            "merely marked down. Marks recover; bookings do not.")
    for d in a["event_days"]:
        findings.append(
            f"{d['date']}: equity {d['d_equity']:+.2f} in one day, of which realized "
            f"{d['d_realized']:+.2f} and marked {d['d_marked']:+.2f}. "
            + ("Realized ROSE while equity FELL -- unrealized loss crystallising as positions "
               "closed, not a fresh market move." if d["d_realized"] > 0 > d["d_equity"] else
               "Both moved together -- a mark move rather than a closing event."))
    for c in a["concentration_events"]:
        findings.append(f"{c['date']}: CONCENTRATION -- {c['note']}. Correlated risk rose while "
                        "the notional number stayed flat, so any check watching only exposure saw "
                        "nothing.")
    if not attributable:
        blocked.append(
            "ATTRIBUTION IMPOSSIBLE: desk_metrics.fills is empty, so funding, basis, slippage and "
            "fees cannot be separated. 'Is this a leak or is this the market?' is NOT answerable "
            "from the data that exists, and naming a cause anyway would be a narrative -- which "
            "gets acted on. Closing this needs per-fill records; it is the same gap the allocator "
            "ranks for execution and costs, and it is cost-1 because the recorder already runs.")
    return {
        "verdict": ("IN LOSS -- CAUSE NOT ATTRIBUTABLE" if a["in_loss"] and not attributable else
                    "IN LOSS" if a["in_loss"] else "NOT IN LOSS"),
        "findings": findings,
        "blocked": blocked,
        "alarm": a["max_drawdown"] >= DRAWDOWN_ALARM,
    }


def find_leaks(a: dict, attributable: bool) -> list[Leak]:
    """Defects in the desk's OWN PLUMBING, each with the fix it warrants.

    A basis that moved against the book is the water, not a leak, and is deliberately absent from
    this list: "fixing" a market loss by turning off the strategy that was working is the classic
    way a desk converts a drawdown into a permanent one. A leak is an unrecorded fill, a stale
    parameter, an unpriced cost, a churn loop, a monitor reading a file nobody writes.
    """
    leaks: list[Leak] = []

    if not attributable:
        leaks.append(Leak(
            id="pnl-unattributable",
            what="P&L cannot be split into market and leak: desk_metrics.fills is empty.",
            evidence=("every equity move is observable and none is explicable. The desk is "
                      f"{a.get('total_pnl', 0):+.2f} over the recorded window and cannot say how "
                      "much of that is funding, basis, slippage or fees."),
            tier=PATCH_READY,
            action=("the executor must INSERT one row per fill into desk_metrics.fills "
                    "(ts, symbol, side, qty, price, fee, funding, order_id, intent) at the point "
                    "it already logs the fill. This is the money path, so it is not autofixed -- "
                    "an analysis organ writing there is exactly what P22 forbids. It is a "
                    "one-function change on a table that already exists and it unblocks "
                    "attribution, the execution derivative and the cost derivative at once."),
            surface="the executor's fill handler",
            verify="desk_metrics.fills row count > 0 on the next cycle; this leak then closes "
                   "itself and the watchdog begins reporting attribution instead of refusing to."))

    days = a.get("days", [])
    if len(days) >= 2:
        span_h = 24.0            # the NAV chain is one attestation per day
        leaks.append(Leak(
            id="pnl-observed-once-daily",
            what=f"P&L is observed every ~{span_h:.0f}h, so a leak is invisible for up to a day.",
            evidence=(f"{len(days) + 1} attestations across {len(days)} day(s); the largest "
                      f"single-day move in the window is "
                      f"{max((abs(d['d_equity']) for d in days), default=0):.2f}, which was "
                      "entirely invisible until the following morning."),
            tier=PATCH_READY,
            action=("emit an intra-day equity mark (the executor already computes one every "
                    "rebalance) so this watchdog runs against a live curve rather than a daily "
                    "snapshot. Same table, higher frequency -- no new plumbing, only a write that "
                    "is currently discarded."),
            surface="the executor's rebalance loop",
            verify="more than one equity observation per calendar day in the source"))

    # AUTOFIX class: churn. Legs rotating at flat notional while realized P&L falls is the desk
    # paying spread to stand still, and `hold_top` exists precisely to damp it -- the config's own
    # note calls it "the churn fix". Only proposed when the evidence is BOOKED losses, because a
    # marked loss is the market and tightening a hold parameter against the market is not plumbing.
    booked = a.get("booked_loss_days", [])
    rotating = [d for d in days if d.get("n_legs", 0) > 0]
    if booked and len(rotating) >= 2:
        legs = [d["n_legs"] for d in rotating]
        if max(legs) - min(legs) >= 2:
            tot = sum(d["d_realized"] for d in booked)
            leaks.append(Leak(
                id="pnl-churn-suspected",
                what="legs rotate while realized P&L falls -- the shape of a churn leak.",
                evidence=(f"leg count moved {min(legs)}..{max(legs)} across the window while "
                          f"{len(booked)} day(s) BOOKED {tot:+.2f} of realized loss. Rotation at "
                          "flat notional pays spread to stand still."),
                tier=BLOCKED,
                action=("cannot be confirmed or fixed without per-fill records: rotation losses "
                        "and adverse basis are indistinguishable in an equity curve, and "
                        "tightening hold_top against a MARKET move would suppress the strategy "
                        "rather than the leak. Unblocked by the same fills patch above -- which "
                        "is why that one is ranked first."),
                surface=CONFIG,
                verify="per-fill realized P&L attributable to rotation vs basis"))
    return leaks


def main() -> int:
    t0 = time.time()
    rows = _rows()
    attributable = _has_fills()
    a = analyse(rows)
    d = diagnose(a, attributable)

    # THE PLUMBING PASS. A watchdog that only alarms consumes attention every cycle, produces
    # nothing, and trains everyone to skim it -- so every leak carries a fix tier and none may
    # rest in "escalated". Autofixes are applied HERE, immediately, on declared live-tunable
    # surfaces only; anything touching the money path is emitted as an exact patch and chased.
    leaks = find_leaks(a, attributable)
    ledger = LeakLedger.load(LEAKS)
    ledger.observe(leaks)
    applied = []
    for leak in leaks:
        if leak.tier == AUTOFIX:
            applied.append({"leak": leak.id, **apply_numeric_config_fix(ROOT, leak)})
    ledger.save(LEAKS)

    stale = [leak for leak in leaks if ledger.age(leak.id) >= LEAK_STALE_CYCLES]

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "source": str(NAV.relative_to(ROOT)),
        "attributable": attributable,
        "analysis": a,
        "diagnosis": d,
        "leaks": [leak.as_dict() | {"cycles_open": ledger.age(leak.id)} for leak in leaks],
        "autofixes_applied": applied,
        "stale_leaks": [leak.id for leak in stale],
        "stale_note": (
            f"{len(stale)} leak(s) have stood open >= {LEAK_STALE_CYCLES} cycles. 'Escalated' is "
            "not a resting state -- a leak parked there is an excuse with a ticket number, and "
            "the audit treats this as a DEFECT rather than a status."
            if stale else ""),
        "fix_posture": (
            "every leak above carries a TIER and an exact action. AUTOFIX lands immediately on a "
            "declared live-tunable surface. PATCH_READY names the precise change and is chased. "
            "BLOCKED names the measurement that unblocks it, and that measurement is chased too. "
            "Nothing is left as 'investigate'."),
        "authority": ("NONE. This reports and alarms; it cannot flatten, resize or halt. Those "
                      "paths belong to the Tier-3 risk rails and are never driven by an analysis "
                      "organ."),
        "next_ceiling": (
            "per-fill attribution (funding / basis / slippage / fees) so a loss can be split into "
            "market and LEAK; then intraday marks so a leak is caught between attestations rather "
            "than a day later; then the same decomposition on shadow and live, not just testnet."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), "utf-8")

    if a.get("state") != "MEASURED":
        print(f"pnl-watch: {a.get('state')} -- {a.get('note', '')[:110]}")
        return 0
    flag = "ALARM" if d["alarm"] else "ok"
    print(f"pnl-watch [{flag}] {a['mode']}: {a['total_pnl']:+.2f} ({a['total_pct']:+.2f}%) "
          f"{a['from']}..{a['to']} | maxDD {a['max_drawdown']:.1%} | {d['verdict']}")
    for f in d["findings"]:
        print(f"  - {f}")
    for b in d["blocked"]:
        print(f"  BLOCKED: {b}")
    for leak in leaks:
        age = ledger.age(leak.id)
        mark = "STALE" if age >= LEAK_STALE_CYCLES else f"x{age}"
        print(f"  LEAK [{leak.tier:11s}|{mark:>5s}] {leak.what}")
        print(f"        FIX: {leak.action[:150]}")
    for f in applied:
        print(f"  AUTOFIX {'APPLIED' if f.get('applied') else 'REFUSED'}: {f}")
    if stale:
        print(f"  {out['stale_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
