#!/usr/bin/env python3
"""IDLE COST FENCE (L1.51) -- every undeployed dollar and every clamp carries a dollar-per-day.

WHY THIS FENCE EXISTS. The doctrine says timidity is "a REAL COMPOUNDING COST reported as loudly
as a risk breach" and that "the burden of proof sits ALWAYS on the conservative choice -- a clamp
must cite QUANTIFIED ruin risk and an explicit lifting condition or be removed". Measured
2026-08-05: NOT ONE CLAMP ON THIS DESK CARRIED A DOLLAR FIGURE. Every risk breach is priced to the
cent and the cost on the other side of the ledger was rhetorical every single time. L1.27 asks of
every delay "am I protecting capital, or avoiding uncertainty?" -- with nothing on one side of the
scale that question could not be answered, only asserted.

THE DEFECT THIS WAS BUILT ON TOP OF, and it is the reason a new fence was needed rather than a
tweak. L1.28a already had a fence. On 2026-08-05 `data/utilisation.json` reported the capital
ceiling as `limit 13151.52, used 13151.52, utilisation 1.0, SATURATED` while
`web/cashcarry_live.json` held `n_carries: 0, deployed_notional: 0.0` -- a book with ZERO
positions reported as fully deployed. `_capital()` passed `live_book_usd()` as numerator and
`_desk_equity_usd()` as denominator, and `live_book_usd()` is the FIRST RUNG INSIDE
`_desk_equity_usd()`, so the ratio was identically 1.0 by construction. The desk's only idleness
law was fenced by a gate structurally incapable of reporting idleness (L1.43). That is fixed in
the same commit as this file; this fence exists because the fixed ceiling still only publishes a
RATIO, and a ratio cannot be weighed against a ruin probability. Dollars can.

CLAMPS ARE NOT ADDITIVE AND THIS FENCE REFUSES TO ADD THEM. Six clamps each blocking 100% of the
book do not cost six times the book. Each clamp publishes `holds_usd` -- what it alone would hold
back -- and the desk-level cost is computed ONCE from total idle capital. Summing per-clamp costs
would produce a large, alarming, WRONG number, and a fence that overstates gets discounted and
then ignored, which is how the thing it measures becomes invisible again.

STATUS VALUES (exit 2 on the first four -- a gate, not a report; every live breach is listed in
`breaches`, never just the headline):
  NO-DATA       the NAV chain is unreadable -- the book is unknown, and unknown is never free.
  NO-FLOOR      neither yield rung is measurable, so nothing can be priced. An unmeasured floor
                is never 0%: a zero floor would price idle capital as free, which is the exact
                assumption L1.28a exists to destroy.
  UNMEASURABLE-PAPER-BOOK  the attestation is `mode: PAPER` and/or `data/LIVE_ENABLE` is absent.
                This is the DEEPEST status and it outranks the rest: a dollar cost derived from a
                MOLDED/SIMULATED curve is what welded the incumbent fence, so this refuses to
                publish one. The honest statement -- the desk has never deployed live capital --
                is louder than any number, not quieter.
  UNPRICED      a clamp is live with no derivable cost or no named lifting condition. THIS IS THE
                ANTI-TIMIDITY BREACH: a clamp nobody can price is a clamp nobody can argue with.
  PRICED        idle capital exists, its cost is published, and every clamp names what lifts it.
  OK            idle capital is below one deployment slice -- nothing material is sitting out.

THIS FENCE LIFTS NOTHING AND SIZES NOTHING. It publishes a number so the adjudication has two
sides. Rails stay untouchable (L1.23); allocation stays a principal decision (L1.6). A survival
rail that costs $1.34/day and prevents ruin is CORRECTLY PAID FOR -- the point is that the desk
should know it is paying, not that it should stop.

    python scripts/check_idle_cost.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: TTL-cached, pages but does not block. A governance fault must never silence
# the only fence that prices the desk's own caution.
from libs.ops.input_provenance import Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import idle_yield as iy  # noqa: E402

#: live_guard runs every few minutes; a guard artifact older than an hour is describing a desk
#: state that has since moved, and its clamps must not be priced as current (L1.44).
_GUARD_MAX_AGE_H = 1.0

_OUT = _ROOT / "data/idle_cost.json"

#: Idle capital below this fraction of equity is not material -- one deployment slice (L1.18a).
_SLICE = 0.10


def _stamp(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    except OSError:
        return None


def _days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return max((datetime.now(tz=UTC) - d).total_seconds() / 86_400.0, 0.0)


def _flat_since(root: Path) -> tuple[str | None, str]:
    """When the book last held a position, from the NAV chain.

    A LOWER BOUND BY CONSTRUCTION, and it says so. The chain starts when attestation started, so
    a book flat before the first row reads as flat only since that row. Reporting a lower bound
    labelled as one is honest; reporting it as the true start would understate every cumulative
    cost derived from it.
    """
    try:
        lines = [ln for ln in (root / "data/nav_attestation.jsonl").read_text(
            "utf-8").splitlines() if ln.strip()]
        rows = [json.loads(ln) for ln in lines]
    except (OSError, ValueError):
        return None, "NAV chain unreadable"
    flat_from = None
    for r in reversed(rows):
        if int(r.get("n_carries") or 0) > 0 or float(r.get("deployed_notional") or 0.0) > 0:
            break
        flat_from = r.get("ts") or r.get("date")
    if flat_from is None:
        return None, "most recent attestation row shows an open book"
    bounded = flat_from == (rows[0].get("ts") or rows[0].get("date"))
    return str(flat_from), ("LOWER BOUND -- the attestation chain begins here, so the book may "
                            "have been flat earlier" if bounded else "last row with an open book")


def _clamps(root: Path, floor_annual: float | None, idle_usd: float,
            paper: bool) -> list[dict[str, Any]]:
    """Every live constraint on deploying capital, each with what it holds and what lifts it.

    `holds_usd` is PER-CLAMP AND NOT ADDITIVE (see module docstring). `usd_per_day` is that clamp's
    holding priced at the reachable floor -- the cost of THIS clamp if it were the only one.
    """
    out: list[dict[str, Any]] = []

    def add(name: str, live: bool, since: str | None, holds: float | None, lifting: str,
            kind: str, note: str = "", *, unmeasured: bool = False) -> None:
        # `unmeasured` exists because `live=False` DELETES the row, and a clamp whose input could
        # not be read is not an absent clamp -- it is an unknown one (L1.55). holds_usd stays None
        # rather than 0.0: a zero holding prices the clamp as FREE, which is the one direction
        # L1.51 forbids ("an unmeasured floor is NEVER 0%").
        if not live and not unmeasured:
            return
        days = _days_since(since)
        per_day = (holds * floor_annual / 365.0) if (
            floor_annual is not None and holds is not None) else None
        out.append({
            "clamp": name,
            "kind": kind,                     # "rail" = L1.23 legitimate; "gate"/"policy" = argue
            "since": since,
            "days_live": round(days, 2) if days is not None else None,
            "holds_usd": None if holds is None else round(holds, 2),
            "usd_per_day": round(per_day, 4) if per_day is not None else None,
            "cumulative_usd": (round(per_day * days, 2)
                               if (per_day is not None and days is not None) else None),
            "lifting_condition": lifting,
            "priced": per_day is not None and days is not None,
            "unmeasured": unmeasured,
            "note": note,
        })

    # --- Gate 0: no live capital has ever been deployed -------------------------------------
    live_enable = (root / "data/LIVE_ENABLE").exists()
    first_capital = None
    try:
        ln = next(x for x in (root / "data/capital_events.jsonl").read_text(
            "utf-8").splitlines() if x.strip())
        first_capital = json.loads(ln).get("at")
    except (OSError, ValueError, StopIteration, KeyError):
        first_capital = None
    add("gate0_not_live", not live_enable, first_capital, idle_usd,
        "data/LIVE_ENABLE present AND data/LIVE_VPS_VERIFIED attested -- a principal act, "
        "not a desk one", "gate",
        "The whole book. Every other clamp below is downstream of this one and cannot bind "
        "until it lifts.")

    # --- Kill switch --------------------------------------------------------------------------
    kill = root / "data/CASHCARRY_KILL"
    add("cashcarry_kill", kill.exists(), _stamp(kill), idle_usd,
        "manual removal after the incident is closed out", "rail",
        "L1.23 survival rail -- legitimately idle headroom, priced so the desk knows what the "
        "protection costs, never to argue it away.")

    # --- Executor risk action -----------------------------------------------------------------
    try:
        live = json.loads((root / "web/cashcarry_live.json").read_text("utf-8"))
    except (OSError, ValueError):
        live = {}
    risk = live.get("risk") or {}
    action = str(risk.get("action") or "")
    flat, flat_why = _flat_since(root)
    add("risk_" + (action or "unknown"), action not in ("", "none", "ok"), flat, idle_usd,
        "; ".join(risk.get("reasons") or []) or "UNNAMED -- no lifting condition on record",
        "rail",
        f"drawdown {risk.get('dd_from_peak_pct')}% from peak. `since` is the book-flat clock "
        f"({flat_why}); the executor stamps no start time on the pause itself, so this is the "
        f"tightest available bound. ABSORBING: a pause with zero positions earns no income, so "
        f"the drawdown ratio it keys on cannot recover on its own.")

    # --- Live-guard ladder and ramp -----------------------------------------------------------
    # L1.55: an UNREADABLE live_guard.json used to ERASE both clamps below rather than unmeasure
    # them -- `entries_allowed` defaulted True (so `not True` = "no ladder clamp") and `frac`
    # defaulted 1.0 ("no ramp clamp"). Both are the loosening direction inside the fence built to
    # price the cost of caution, so a dead guard read as a FREER desk than a live one. The
    # provenance decides which of "no clamp" and "cannot tell" gets published.
    lg_inp = Inputs("check_idle_cost.live_guard")
    lg = lg_inp.read_json(root / "data/live_guard.json", default={}, max_age_h=_GUARD_MAX_AGE_H)
    if not isinstance(lg, dict):
        lg_inp.defaulted("data/live_guard.json", "artifact is not a JSON object")
        lg = {}
    guard_measured = lg_inp.measured()
    ladder = lg.get("ladder") or {}
    unacked = ladder.get("unacked_since")
    ladder_since = None
    if isinstance(unacked, (int, float)) and unacked > 0:
        ladder_since = datetime.fromtimestamp(float(unacked), tz=UTC).isoformat()
    if not guard_measured:
        # ONE row for both guard clamps: their state is unknown, which is neither "clamped" nor
        # "free". Emitted UNPRICED so it reads as a defect to close, not as a zero cost.
        add("guard_clamps", False, None, None,
            f"{lg_inp.why()} -- the ladder and ramp clamps cannot be priced until "
            f"data/live_guard.json is readable (producer: scripts/run_live_guard.py)",
            "gate", "ladder and ramp state UNKNOWN -- not zero (L1.55)", unmeasured=True)
    else:
        add("guard_ladder_" + str(ladder.get("rung") or "unknown"),
            not ladder.get("entries_allowed", True), ladder_since, idle_usd,
            "manual re-arm" if ladder.get("requires_manual_rearm") else "ladder rung recovery",
            "rail", f"size_multiplier {ladder.get('size_multiplier')}")

    ramp = lg.get("ramp") or {}
    # Absent/unparseable reads as 1.0 (no clamp), but a genuine 0.0 must SURVIVE as 0.0 -- a fully
    # disarmed ramp is the largest clamp on the board, and `float(x or 1.0)` would erase exactly
    # that case while looking correct. The absent-file case is handled by `guard_measured` above.
    raw = ramp.get("size_fraction")
    frac = 1.0
    if isinstance(raw, (int, float, str)):
        try:
            frac = float(raw)
        except ValueError:
            frac = 1.0
    if guard_measured:
        add("ramp_size_fraction", frac < 1.0, lg.get("ts"), idle_usd * (1.0 - frac),
            ramp.get("why") or "UNNAMED -- no lifting condition on record", "gate",
            f"pinned at {frac:.2f}; holds the fraction of the book the ramp will not yet size. "
            f"Its step-up inputs are produced by scripts/run_cost_identification.py -- the gate "
            f"cannot advance by waiting (L1.45).")

    if paper:
        for c in out:
            c["usd_per_day"] = None
            c["cumulative_usd"] = None
            c["priced"] = False
            c["note"] = (c["note"] + " " if c["note"] else "") + (
                "UNPRICEABLE while the book is PAPER: `holds_usd` derives from a MOLDED curve, "
                "not a balance.")
    return out


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    cost = iy.idle_cost(root)
    bs, fl = cost["book"], cost["floor"]
    breaches: list[str] = []
    floor_annual = fl.get("annual_rate")
    clamps = _clamps(root, floor_annual, float(bs.get("idle_usd") or 0.0),
                     bool(bs.get("is_paper")) or not bs.get("measurable"))

    # STATUS LADDER, deepest first. Order matters: a paper book cannot produce a trustworthy
    # clamp price, so PAPER outranks UNPRICED rather than being masked by it.
    if not bs.get("source") or bs.get("source") == "unreadable":
        status = "NO-DATA"
        breaches.append("the NAV attestation chain is unreadable -- the book is unknown")
    elif not fl.get("measurable"):
        status = "NO-FLOOR"
        breaches.append("no yield rung is measurable: " + "; ".join(fl.get("notes") or []))
    elif cost["status"] == "UNMEASURABLE-PAPER-BOOK":
        status = "UNMEASURABLE-PAPER-BOOK"
        breaches.append(bs["why"])
    else:
        unpriced = [c["clamp"] for c in clamps if not c["priced"]]
        unnamed = [c["clamp"] for c in clamps if "UNNAMED" in str(c["lifting_condition"])]
        idle_frac = (float(bs["idle_usd"]) / float(bs["equity_usd"])
                     if bs.get("equity_usd") else 0.0)
        if unpriced or unnamed:
            status = "UNPRICED"
            for c in unpriced:
                breaches.append(f"clamp {c!r} is live with no derivable cost")
            for c in unnamed:
                breaches.append(f"clamp {c!r} names no lifting condition -- "
                                "the doctrine requires one or its removal")
        elif idle_frac < _SLICE:
            status = "OK"
        else:
            status = "PRICED"

    live_clamps = [c for c in clamps if c["kind"] != "rail"]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.51 -- an undeployed dollar and an unpriced clamp are the same unbooked loss. "
               "Every clamp carries a dollar-per-day and a lifting condition, or it is a defect.",
        "status": status,
        "book": bs,
        "floor": fl,
        "usd_per_day": cost.get("usd_per_day"),
        "usd_per_year": cost.get("usd_per_year"),
        "hypothetical_usd_per_day": cost.get("hypothetical_usd_per_day"),
        "hypothetical_usd_per_year": cost.get("hypothetical_usd_per_year"),
        "clamps": clamps,
        "n_clamps": len(clamps),
        "n_non_rail_clamps": len(live_clamps),
        "not_additive": "Per-clamp usd_per_day is what THAT clamp alone would hold. Clamps "
                        "overlap; summing them multiply-counts the same dollars. The desk-level "
                        "cost is the top-level usd_per_day, computed once from total idle.",
        "breaches": breaches,
        "why": cost.get("why"),
        "next_action": _next_action(status, clamps),
    }


def _next_action(status: str, clamps: list[dict[str, Any]]) -> str:
    if status == "UNMEASURABLE-PAPER-BOOK":
        return ("Answer the one question that decides whether this meter ever reads non-zero: "
                "WHERE DOES THE PRINCIPAL-SIGNED $5,757.08 ACTUALLY SIT, and is it already "
                "earning at or above the reachable floor there? If yes, this meter is a constant "
                "zero and should be retired (its own falsifier (a)). That is a question for the "
                "principal and costs nothing to ask.")
    if status == "UNPRICED":
        bad = [c["clamp"] for c in clamps if not c["priced"]
               or "UNNAMED" in str(c["lifting_condition"])]
        return f"name a lifting condition and a start stamp for: {', '.join(bad)}"
    if status == "NO-FLOOR":
        return ("restore data/hurdle_rate.json or data/defi_lending.jsonl -- with neither rung "
                "measurable the desk cannot say what idle capital costs")
    if status == "PRICED":
        return ("carry each clamp's usd_per_day into its GAP_REGISTER row and ledger row, so "
                "every deferral is argued against an accruing number (L1.27)")
    return "none -- idle capital is below one deployment slice"


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        fl, bk = rep["floor"], rep["book"]
        print(f"idle cost (L1.51): {rep['status']}")
        print(f"  book: equity ${bk['equity_usd']:,.2f} | deployed ${bk['deployed_usd']:,.2f} "
              f"across {bk['n_positions']} position(s) | idle ${bk['idle_usd']:,.2f} "
              f"| mode {bk['mode']!r}")
        if fl.get("annual_rate") is not None:
            print(f"  floor: {fl['annual_rate'] * 100:.2f}%/yr via {fl['winner']} "
                  f"(risk-free {(fl['risk_free_annual'] or 0) * 100:.2f}% vs lending net "
                  f"{(fl['lending_net_annual'] or 0) * 100:.2f}% = gross "
                  f"{(fl['lending_gross_annual'] or 0) * 100:.2f}% - {fl['haircut_bps']:.0f}bps; "
                  f"breakeven haircut {fl['breakeven_haircut_bps']}bps)")
        if rep.get("usd_per_day") is not None:
            print(f"  COST: ${rep['usd_per_day']:.2f}/day  (${rep['usd_per_year']:,.2f}/yr)")
        elif rep.get("hypothetical_usd_per_day") is not None:
            print(f"  cost: REFUSED on a paper book. Hypothetical if the attested figure were a "
                  f"balance: ${rep['hypothetical_usd_per_day']:.2f}/day "
                  f"(${rep['hypothetical_usd_per_year']:,.2f}/yr)")
        for c in rep["clamps"]:
            pd = f"${c['usd_per_day']:.2f}/day" if c["usd_per_day"] is not None else "UNPRICED"
            print(f"  clamp {c['clamp']:<34} [{c['kind']:<6}] {pd:>14}  "
                  f"{(str(c['days_live']) + 'd') if c['days_live'] is not None else '?d':>7}  "
                  f"lifts on: {c['lifting_condition'][:78]}")
        for b in rep["breaches"]:
            print(f"  BREACH: {b}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return 2 if rep["status"] not in ("OK", "PRICED") else 0


if __name__ == "__main__":
    sys.exit(main())
