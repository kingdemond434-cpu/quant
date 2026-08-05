#!/usr/bin/env python3
"""MECHANISM ATTRIBUTION (R0137) -- a sleeve may not read as SURVIVED on P&L its mechanism
cannot explain.

WHAT PRODUCED THIS FENCE, on 2026-07-31. The dashboard showed funding carry as a survivor. The
numbers behind it:

    equity $18,669 from $15,000  ->  net +$3,669.55 (+24.5%) over 29 days, Sharpe 13.13
    FUNDING HARVEST COLLECTED:   +$113.06

Funding is 3.1% of the P&L. The other $3,556 did not come from carry. A cash-and-carry book is
spot-long / perp-short and delta-neutral BY CONSTRUCTION: its price legs cancel, so its P&L should
be funding plus basis, near-100%. The desk already owns the fence that says this --
``libs.execution.carry_accounting.carry_bleed_report``, deliberately TWO-SIDED so that a large
POSITIVE non-funding P&L alarms as loudly as a loss, because on a hedged book a windfall that size
is a NAKED LEG rather than edge. Run on those numbers it returns:

    BLEED(inverted): non-funding PnL +3556.49 is 3146% of +113.06 funding harvest

So the desk's own logic already disagreed with the dashboard. The verdict was computed, written to
a JSON field, rendered -- AND GATED NOTHING. `max_audit` raises a defect only when funding is
UNMEASURED; when the alarm actually trips, nothing fails. That is the recurring defect shape on
this desk in its most expensive form: a fence firing into a field nobody reads, while a survival
claim built on the same numbers goes to the principal for a capital decision.

WHY IT IS A SEPARATE, GENERAL FENCE. The specific bug is one `if` in max_audit. The general bug is
that ANY sleeve can be credited with P&L its stated mechanism does not explain -- a hedge with an
untracked leg, a market-neutral book carrying beta, or a sleeve's line item quietly aggregating an
account it does not own. So the rule is stated once and applied to every sleeve with a measurable
mechanism term:

    A sleeve whose P&L is not attributable to its stated mechanism is UNATTRIBUTED. It may not
    read as survived, validated or promotable, whatever its return looks like -- and an
    unattributed WIN is treated exactly as seriously as an unattributed loss, because the
    directional exposure that produced it is still there and still unhedged.

UNMEASURED never reads as OK: a venue income read that failed makes attribution UNDECIDABLE, not
clean, and the fence says so rather than passing.

    python scripts/check_mechanism_attribution.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: ATTRIBUTED is this fence's OK. UNMEASURED -- no rows, or every sleeve's mechanism term
#: unreadable -- previously exited 0, so "we cannot tell whether any edge is attributed" was
#: reported to cron as "every edge is attributed" (L1.16, L1.28a).
_PASSING = frozenset({"ATTRIBUTED"})

_OUT = "data/mechanism_attribution.json"

#: How much of a sleeve's P&L may come from outside its stated mechanism before the claim is
#: UNATTRIBUTED. 0.5 matches carry_bleed_report's own alert_frac -- the same number the desk
#: already chose for the same question, reused rather than re-picked (see check_sizing_derivation).
UNATTRIBUTED_FRAC = 0.5

#: Sleeves with a MEASURABLE mechanism term, and where to read it. A sleeve whose mechanism cannot
#: be measured separately from its P&L is not listed: it would be judged by a number that does not
#: exist, which is worse than not judging it. That absence is itself reported.
_SLEEVES: dict[str, dict[str, str]] = {
    "cash_and_carry": {
        "mechanism": "funding harvest on a delta-neutral spot/perp pair; price legs cancel by "
                     "construction, so P&L should be funding + basis, near-100%",
        "total_key": "net_pnl",
        "mechanism_key": "funding",
    },
}


def attribute(name: str, spec: dict[str, str], state: dict[str, Any]) -> dict[str, Any]:
    total = state.get(spec["total_key"])
    mech = state.get(spec["mechanism_key"])
    row: dict[str, Any] = {"sleeve": name, "mechanism": spec["mechanism"],
                           "total_pnl": total, "mechanism_pnl": mech}
    if total is None or mech is None:
        return {**row, "state": "UNMEASURED",
                "why": (f"missing {spec['total_key'] if total is None else spec['mechanism_key']} "
                        "-- attribution is UNDECIDABLE, which is not the same as clean")}
    try:
        total, mech = float(total), float(mech)
    except (TypeError, ValueError):
        return {**row, "state": "UNMEASURED", "why": "non-numeric P&L terms"}

    unexplained = round(total - mech, 2)
    row["unexplained_pnl"] = unexplained
    row["mechanism_share"] = round(mech / total, 4) if total else None
    if mech > 0:
        ratio = abs(unexplained) / mech
        bad = ratio >= UNATTRIBUTED_FRAC
    else:
        ratio = float("inf") if unexplained != 0 else 0.0
        bad = unexplained != 0.0
    row["unexplained_vs_mechanism"] = (None if ratio == float("inf") else round(ratio, 3))
    if not bad:
        share = row["mechanism_share"]
        return {**row, "state": "ATTRIBUTED",
                "why": (f"{share:.0%} of P&L explained by the stated mechanism" if share is not None
                        else "no P&L to attribute -- nothing earned, nothing unexplained")}
    direction = "WIN" if unexplained > 0 else "LOSS"
    return {**row, "state": "UNATTRIBUTED",
            "why": (f"unexplained {direction} {unexplained:+,.2f} is "
                    + (f"{ratio:.0%} of " if ratio != float("inf") else "present with no ")
                    + f"the {mech:+,.2f} mechanism term -- this sleeve is being credited with P&L "
                      "its mechanism cannot produce. An unexplained WIN is not better news than a "
                      "loss: the exposure that made it is still on, still unhedged, and will "
                      "reverse. NOT survived, NOT promotable, whatever the return looks like.")}


#: Where a deployed-state blob may live, in priority order. The second entry was
#: data/cashcarry_state.json (R0333) -- a path NO organ writes, so the fallback could never fire
#: and its silence was indistinguishable from a healthy read. The executor publishes its book
#: state at data/cashcarry_positions.json (run_cashcarry_executor.py:43).
_STATE_CANDIDATES = ("research_state.json", "data/cashcarry_positions.json")

#: A blob is a deployed-state artifact only if it carries a deployed/molded block or at least one
#: sleeve-shaped key. Treating ANY readable JSON object as the deployed state is how a positions
#: file becomes a silent, sleeve-less "clean" attribution.
_SHAPE_KEYS = ("sleeves", "live_sleeves", "net_pnl", "funding")


def _load_state(root: Path, rel: str) -> tuple[dict[str, Any] | None, str]:
    """One deployed-state candidate, with the failure NAMED (R0333).

    "absent", "unparseable" and "schema-missing-key" are three different facts and the fence
    reports which one it hit -- an UNDECIDABLE attribution must say WHY it is undecidable, or the
    next reader assumes the artifact simply had nothing to report.
    """
    try:
        raw = (root / rel).read_text("utf-8")
    except FileNotFoundError:
        return None, f"{rel}: absent"
    except OSError as exc:
        return None, f"{rel}: unreadable ({type(exc).__name__})"
    try:
        blob = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"{rel}: unparseable (not valid JSON, line {exc.lineno})"
    if not isinstance(blob, dict):
        return None, f"{rel}: unparseable (holds a {type(blob).__name__}, not an object)"
    for key in ("deployed", "molded"):
        block = blob.get(key)
        if isinstance(block, dict) and block:
            return block, "ok"
    if any(k in blob for k in _SHAPE_KEYS):
        return blob, "ok"
    return None, (f"{rel}: schema-missing-key (no deployed/molded block and none of "
                  f"{', '.join(_SHAPE_KEYS)} -- not a deployed-state artifact)")


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    src: str | None = None
    deployed: dict[str, Any] = {}
    why: list[str] = []
    for cand in _STATE_CANDIDATES:
        blob, verdict = _load_state(root, cand)
        if blob is not None:
            src, deployed = cand, blob
            break
        why.append(verdict)
    if src is None:
        return {"generated": datetime.now(tz=UTC).isoformat(), "status": "UNMEASURED",
                "detail": "no deployed-state artifact readable on this host -- attribution "
                          "UNDECIDABLE, which never reads as clean; " + "; ".join(why),
                "n_sleeves": 0, "sleeves": []}

    named = list(deployed.get("sleeves") or deployed.get("live_sleeves") or [])
    rows = []
    for name, spec in _SLEEVES.items():
        if named and not any(name in str(s) for s in named):
            continue                                   # this sleeve is not deployed here
        rows.append(attribute(name, spec, deployed))
    unjudged = [str(s) for s in named
                if not any(k in str(s) for k in _SLEEVES) and "paper" not in str(s)]

    bad = [r for r in rows if r["state"] == "UNATTRIBUTED"]
    unmeasured = [r for r in rows if r["state"] == "UNMEASURED"]
    status = ("UNATTRIBUTED" if bad else "UNMEASURED" if unmeasured or not rows else "ATTRIBUTED")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "source": src,
        "law": "L1.6/L2.6 -- a sleeve may not read as survived on P&L its stated mechanism cannot "
               "explain. An unattributed WIN is as disqualifying as an unattributed loss: the "
               "exposure that produced it is unhedged and will reverse.",
        "status": status,
        "n_sleeves": len(rows), "n_unattributed": len(bad),
        "sleeves": rows,
        "mechanism_unjudgeable": unjudged,
        "detail": (f"{len(rows)} sleeve(s) with a measurable mechanism term"
                   + (f"; UNATTRIBUTED: {', '.join(r['sleeve'] for r in bad)}" if bad else "")
                   + (f"; UNMEASURED: {', '.join(r['sleeve'] for r in unmeasured)}"
                      if unmeasured else "")
                   + (f"; no mechanism term to judge: {', '.join(unjudged)}" if unjudged else "")),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"mechanism attribution (L1.6): {rep['status']} -- {rep['detail']}")
        for r in rep["sleeves"]:
            if r["state"] != "ATTRIBUTED":
                print(f"  {r['sleeve']}: {r['state']} -- {r['why']}")
    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING)


if __name__ == "__main__":
    sys.exit(main())
