#!/usr/bin/env python3
"""FUNDING CAPTURE FENCE (L1.47) -- the desk optimises how LONG to hold a carry and has never
once asked WHERE in the funding cycle to open or close one.

WHY THIS FENCE EXISTS. Funding is a DISCRETE payment at fixed UTC stamps. The executor books it
as a CONTINUOUS accrual -- `est_funding = funding * notl * (held / 8.0)`
(run_cashcarry_executor.py:870) -- and that booking is UNBIASED IN EXPECTATION, which is exactly
why it survived every review this desk has ever run. Measured on the 265-close tape: mean delta
-0.013 settlements, per-trade sd 0.482. The average is right. No single trade is.

Three layers hid it, each individually reasonable:
  1. THE ACCOUNTING BOOKS THE EXPECTATION, so it cannot show the coin flip. Per-trade sd is 0.491
     settlements and 43.3% of closes are mis-marked by half a settlement or more.
  2. REALISED FUNDING EXISTS ONLY AS A BOOK-LEVEL SCALAR -- `out["funding"] += amt`
     (binance_live.py:251) has no symbol key, so `carry_accounting` differences it at book level
     and any phase error lands in the EXECUTION bucket, where R0219 is currently hunting a ~66bps
     gap it cannot possibly find there.
  3. THE CLOCK IS FETCHED AND DISCARDED. `nextFundingTime` arrives in the very
     `/fapi/v1/premiumIndex` payload the desk already reads every cycle (crypto_source.py:144)
     and had ZERO occurrences repo-wide, alongside `fundingIntervalHours` -- which is 4h for many
     high-funding alts, so every `/ 8.0` under-counts exactly the best names by 2x.

WHAT THE FIRST RUN FOUND (2026-08-01, 265 real closes): opens and closes BOTH concentrate in the
final hour before a settlement at z = +6.3 and +5.2. For opens that is free money; for closes it
is the worst phase available -- walking away minutes before a payment already earned by ~8h of
borne basis risk. THE MECHANISM IS UNESTABLISHED and this fence does not pretend otherwise: three
candidates were tested and REFUTED on 2026-08-01 (cron alignment -- the executor is a continuous
systemd service, not a cron job; signal-coupling -- funding at open is flat across phase, oct7
median 1.00 vs 1.02 bps; min-hold aliasing -- close octile equals open octile only 8.7% of the
time, BELOW the 12.5% chance rate). A measured fact with a refuted story is still a measured fact.

FENCE STATUS (exit 2 on the first four -- a gate, not a report; ALL live breaches are always
listed in `breaches`, never just the headline):
  NO-DATA      execution tape absent or unreadable -- nothing can be measured.
  UNMEASURED   no PER-POSITION venue truth exists. The desk books an ESTIMATE of funding and has
               never once differenced it against what Binance actually paid. This is the deepest
               status and it outranks the rest: every other number here is computed from the
               estimate. Clears when `funding_events()` lands (money-path, L1.38-frozen).
  FORFEITING   closes concentrate in the pre-settlement window beyond chance -- the desk is
               systematically walking away from imminent payments.
  PHASE-BLIND  close rows carry no rail/reason field, so a forfeit cannot be attributed to a
               CHOICE versus a forced rail exit. The executor KNOWS (`_churn_guard` takes
               `rail_forced`) and discards it at log time, which makes the controllability
               question -- this capability's own falsifier -- unanswerable after the fact.
  OK           truth differenced against estimate, no pre-stamp concentration, closes attributable.

THIS FENCE MAY NEVER REPORT OK BECAUSE IT FOUND NOTHING TO LOOK AT. An empty tape and an absent
ground truth are LOUDER than a healthy desk, never quieter (L1.28a).

    python scripts/check_funding_capture.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: TTL-cached, pages but does not block -- a governance fault must never
# silence the fence reporting on the revenue line of the desk's only deployed sleeve.
from libs.execution import execution_tape  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import funding_clock as fc  # noqa: E402

#: Hours before a settlement inside which a close forfeits a near-certain payment. One hour at an
#: 8h interval = the final octile, so the null is P = 1/8 and the test is an exact binomial.
FORFEIT_WINDOW_H = 1.0

#: Pre-registered. A concentration this large is not a sampling accident; below it the fence says
#: nothing rather than manufacturing a finding from noise.
FORFEIT_Z = 3.0

#: Per-trade mis-marking above this share means the accrual is not merely imprecise but routinely
#: wrong by a material fraction of a whole payment.
MISMARK_FRACTION = 0.25

#: Fields that would let a close be attributed to a choice versus a forced rail exit. None of
#: these is currently written; the check is by presence, so it self-clears the day one appears.
_ATTRIBUTION_FIELDS = ("rail_forced", "reason", "close_reason")


def _truth_rows(root: Path) -> list[dict[str, Any]] | None:
    """PER-POSITION realised funding from the venue, or None when it has never been collected.

    None is NOT an error and NOT OK: it is the UNMEASURED finding. The producer is a
    `funding_events()` twin of the working `commission_events()` (binance_testnet.py:269), which
    is a money-path change and therefore staged while the launch window is STERILE (L1.38).
    """
    path = root / "data/funding_truth.json"
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rows = data.get("events") if isinstance(data, dict) else data
    return rows if isinstance(rows, list) else None


def _closes(tape: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in tape
            if r.get("event") == "close" and r.get("opened") and r.get("closed")]


def _parse(stamp: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def _num(v: Any) -> float | None:
    """Coerce a tape field to a float, or None when the row is malformed.

    Returns None rather than 0.0 so a junk value is COUNTED as malformed instead of silently
    becoming a zero -- a zero funding rate reads as 'this close forfeited nothing', which is the
    reassuring direction and therefore the dangerous one.
    """
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _binomial_z(k: int, n: int, p: float) -> float:
    """Excess concentration in sigmas. Zero for an empty sample -- never a divide-by-zero."""
    if n <= 0:
        return 0.0
    return (k - n * p) / math.sqrt(n * p * (1.0 - p))


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Pure: read tape + truth, return the verdict. No writes -- tests call it directly."""
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)

    tape = execution_tape.read(path=root / "data/moat/execution_tape/cashcarry_trades.jsonl")
    closes = _closes(tape)
    truth = _truth_rows(root)

    n = 0
    malformed = 0
    mismarked = 0
    zero_capture = 0
    forfeits = 0
    forfeit_usd = 0.0
    forfeit_notional = 0.0
    total_notional = 0.0
    booked_funding = 0.0
    deltas: list[float] = []
    phase_octiles = [0] * 8

    for r in closes:
        t0, t1 = _parse(r.get("opened")), _parse(r.get("closed"))
        rate, notl = _num(r.get("funding_rate")), _num(r.get("notional"))
        est = _num(r.get("est_funding"))
        if t0 is None or t1 is None or rate is None or notl is None:
            # A row the fence cannot read is COUNTED and surfaced, never skipped silently and
            # never coerced to a comfortable zero (L2.4).
            malformed += 1
            continue
        n += 1
        total_notional += notl
        booked_funding += est or 0.0

        discrete = fc.settlements_in(t0, t1)
        continuous = fc.continuous_settlements(t0, t1)
        deltas.append(discrete - continuous)
        if abs(discrete - continuous) >= 0.5:
            mismarked += 1
        if discrete == 0 and abs(est or 0.0) > 0.0:
            zero_capture += 1

        phase_octiles[min(7, int(fc.phase_hours(t1)))] += 1
        if fc.hours_to_settlement(t1) <= FORFEIT_WINDOW_H and rate > 0.0:
            forfeits += 1
            forfeit_usd += rate * notl
            forfeit_notional += notl

    p_null = FORFEIT_WINDOW_H / fc.DEFAULT_INTERVAL_H
    forfeit_z = _binomial_z(forfeits, n, p_null)
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
    sd_delta = (math.sqrt(sum((d - mean_delta) ** 2 for d in deltas) / (len(deltas) - 1))
                if len(deltas) > 1 else 0.0)
    mismark_frac = mismarked / n if n else 0.0
    attributable = any(f in r for r in closes for f in _ATTRIBUTION_FIELDS)

    # ALL live breaches, never first-failure-only: a gate that hides breaches behind one headline
    # gets run once and disbelieved (L1.37).
    breaches: list[str] = []
    if truth is None:
        breaches.append("UNMEASURED: no per-position realised funding has ever been collected")
    if n and forfeit_z >= FORFEIT_Z:
        breaches.append(f"FORFEITING: {forfeits}/{n} closes inside {FORFEIT_WINDOW_H:g}h of a "
                        f"settlement (z=+{forfeit_z:.1f})")
    if n and mismark_frac >= MISMARK_FRACTION:
        breaches.append(f"MIS-MARKED: {mismark_frac:.1%} of closes booked >=0.5 settlement wrong")
    if closes and not attributable:
        breaches.append("PHASE-BLIND: close rows carry no rail/reason field")
    if malformed:
        breaches.append(f"UNREADABLE: {malformed} close row(s) unparseable and excluded")

    if not tape:
        status = "NO-DATA"
        detail = "execution tape is empty or unreadable -- funding capture cannot be measured"
    elif not closes:
        status = "NO-DATA"
        detail = f"{len(tape)} tape rows but ZERO closes -- nothing has completed a round trip"
    elif truth is None:
        status = "UNMEASURED"
        detail = (f"no per-position venue truth: {n} closes booked ${booked_funding:.2f} of "
                  f"ESTIMATED funding and not one has been differenced against what Binance "
                  f"actually paid (mean delta {mean_delta:+.3f} settlements, sd {sd_delta:.3f}, "
                  f"{mismark_frac:.1%} mis-marked by >=0.5)")
    elif forfeit_z >= FORFEIT_Z:
        status = "FORFEITING"
        detail = (f"{forfeits}/{n} closes ({forfeits / n:.1%}) landed within "
                  f"{FORFEIT_WINDOW_H:g}h of a settlement with positive funding (z=+{forfeit_z:.1f}, "
                  f"null {p_null:.1%}) -- ${forfeit_usd:.2f} of imminent payment walked away from")
    elif not attributable:
        status = "PHASE-BLIND"
        detail = ("close rows carry no rail/reason field, so a pre-stamp close cannot be "
                  "attributed to a CHOICE versus a forced exit -- the executor knows "
                  "(`_churn_guard(rail_forced)`) and discards it at log time")
    else:
        status = "OK"
        detail = (f"{n} closes differenced against venue truth; pre-stamp concentration "
                  f"z=+{forfeit_z:.1f} below the {FORFEIT_Z:g} bar")

    return {
        "generated": now.isoformat(),
        "law": ("L1.47 -- funding is a DISCRETE payment; the phase of the funding cycle is a free "
                "control variable with the same P&L units as hold duration, and the desk must "
                "measure its capture rather than book its expectation"),
        "status": status,
        "detail": detail,
        "breaches": breaches,
        "n_tape_rows": len(tape),
        "n_closes": n,
        "n_malformed_closes": malformed,
        "per_position_truth_rows": None if truth is None else len(truth),
        "mean_delta_settlements": round(mean_delta, 4),
        "sd_delta_settlements": round(sd_delta, 4),
        "mismarked_ge_half_settlement": mismarked,
        "mismarked_fraction": round(mismark_frac, 4),
        "closes_booking_funding_with_zero_settlements": zero_capture,
        "close_phase_octiles": phase_octiles,
        "forfeit_window_h": FORFEIT_WINDOW_H,
        "n_forfeit_closes": forfeits,
        "forfeit_z": round(forfeit_z, 2),
        "forfeit_usd": round(forfeit_usd, 2),
        "forfeit_bps_on_affected_notional": (
            round(forfeit_usd / forfeit_notional * 1e4, 2) if forfeit_notional else None),
        "forfeit_share_of_booked_funding": (
            round(forfeit_usd / booked_funding, 4) if booked_funding else None),
        "booked_funding_usd": round(booked_funding, 2),
        "total_notional_usd": round(total_notional, 2),
        "closes_attributable": attributable,
        "next_action": (
            "Collect fills -- no round trip has completed"
            if status == "NO-DATA" else
            "Land funding_events() (a ~15-line twin of commission_events) and write "
            "data/funding_truth.json -- MONEY PATH, staged while the launch window is STERILE"
            if status == "UNMEASURED" else
            "Make closes settlement-aware: hold past an imminent stamp when funding is positive "
            "and no rail is forcing the exit -- MONEY PATH, stage until the window opens"
            if status == "FORFEITING" else
            "Persist `rail_forced` onto the close log row so forfeits can be attributed"
            if status == "PHASE-BLIND" else
            "Hold the floor: capture efficiency is a ratchet metric (L1.0)"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/funding_capture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"funding capture (L1.47): {rep['status']} -- {rep['detail']}")
        print(f"  closes {rep['n_closes']} | mis-marked {rep['mismarked_fraction']:.1%} | "
              f"pre-stamp z=+{rep['forfeit_z']} | truth rows {rep['per_position_truth_rows']}")
        print(f"  close phase octiles (0=just after a stamp, 7=final hour before one): "
              f"{rep['close_phase_octiles']}")
        for b in rep["breaches"]:
            print(f"  BREACH: {b}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return 2 if rep["status"] != "OK" else 0


if __name__ == "__main__":
    sys.exit(main())
