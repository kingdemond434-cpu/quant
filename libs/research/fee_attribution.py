"""FEE ATTRIBUTION FROM VENUE TRUTH -- what the trade tape structurally cannot answer.

THE GAP (R0371). `web/cashcarry_live.json` attributes $1,750.88 of futures commission, which is
88.7% of the sleeve's entire non-funding loss. The desk can therefore see that FEES ARE THE
DOMINANT LOSS and could not say which symbol paid them: 0 of 500 rows in
`data/cashcarry_trades.json` carry `fee`/`commission`/`fee_usd`, because `_tca()` records
slippage-vs-mid and no commission term at all.

THE ROW'S OWN FIX WAS NOT THE BINDING ONE. R0371 proposed stamping commission onto the close row
at fill time. That is necessary but not sufficient, and this module exists because measuring the
gap first changed the answer:

  * `binance_testnet.commission_events()` ALREADY reads per-event commission, paginated through
    the audited `_income_rows` path, and had ZERO callers repo-wide. The capability was built and
    never wired -- so the first repair is a consumer, not a new producer.
  * A fill-time stamp would price only what the tape logs, and the tape logs ~7% of the notional
    the fee bill implies (see `coverage`). Stamping alone would have produced a confident,
    well-formed, 7%-complete cost model.

WHAT RECONCILES AND WHAT DOES NOT -- measured 2026-08-12, not asserted:

  RECONCILES EXACTLY. Per-symbol attribution. 11,194 commission events over 2026-07-02..08-01 sum
  to 1750.8780 USDT against the dashboard's 1750.88. Concentration is the finding: COOKIEUSDT,
  1000CATUSDT, MOVEUSDT and TSTUSDT carry 85.9% of the entire fee bill. The sleeve does not have
  a broad fee drag; it has four names.

  REFUSED. Row-level (per-round-trip) attribution. The income ledger emits one COMMISSION row per
  PARTIAL fill -- up to 48 events share a single timestamp and the median inter-event gap is 1s --
  so events do not align to the tape's fill instants: the median gap from an event to the nearest
  same-symbol tape instant is 15,407s (4.3h), p95 22.8h. A nearest-in-time join at that separation
  would assign fees to round trips essentially at random. `attribute()` therefore returns
  per-symbol truth and REFUSES the per-row join rather than fabricating a precise-looking number.
  Restoring it needs a fill-time stamp (the R0371 half that survives), not a better join.

  UNMEASURED, NEVER ZERO. The spot leg. The spot testnet account has been reset -- `my_trades`
  returns 0 rows for every historical window and balances are round-number reseeded -- so spot
  commission is UNRECOVERABLE, which is a different claim from "spot paid no fees". Callers get
  `spot_leg="UNMEASURED"` and no number (L1.28a; WS-005, the desk's most-repeated defect class).

  UNEXPLAINED, AND REPORTED AS SUCH. At the venue's own 5bp taker rate the bill implies ~$3.50M of
  traded futures notional; the tape's rows total $248k (7.1%). 99.1% of commission falls inside the
  tape's window and on symbols the tape knows, so this is not a window or universe mismatch -- the
  tape is missing trading it did, not trading it never saw. `run_cashcarry_executor.py` declines to
  log a row on the OPEN-FAIL/CLOSE-FAIL paths (both `continue` before `_log_trade`), so commission
  paid on a partially-filled unconfirmed order leaves no tape record at all. That is a CANDIDATE
  mechanism, not a proven one, and `residual_note` says so: a measured gap with an unproven story
  is still a measured gap (L1.47).

Pure and offline. Every function here takes data and returns data; the venue read lives in
`scripts/run_fee_attribution.py`. Commission is POSITIVE-MEANS-PAID throughout, matching `_tca`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

#: Binance USDM taker commission on the desk's own account, measured from a real fill rather than
#: assumed: COOKIEUSDT quoteQty 887.0092 billed 0.44350460 -> exactly 5.0bp. Used ONLY to turn the
#: fee bill into an implied notional. Maker fills are cheaper, so the implied notional this yields
#: is a LOWER BOUND on what was actually traded -- the coverage gap it measures can only widen.
TAKER_RATE = 0.0005

#: Events at or below this share a single order's sweep and are partial fills, not round trips.
#: Kept as a named constant because it is the number that decides `row_level` is refused.
PARTIAL_FILL_NOTE = "income ledger emits one COMMISSION row per partial fill"


def _f(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def fill_instant(row: Mapping[str, Any]) -> datetime | None:
    """The moment ``row``'s fill actually happened, or None when the tape cannot locate it.

    open  -> `opened` is stamped at fill time.
    close -> `closed` is stamped at fill time.
    topup -> NEITHER. `_log_trade` passes `p.get("opened")` for a topup, so the row carries the
             POSITION's original open time, not the topup's fill time (verified: 51/51 topup rows
             carry a stamp equal to an open row's). A topup is therefore unlocatable in time from
             the tape alone, and this returns None rather than a stamp that is hours wrong.
    """
    ev = str(row.get("event") or "")
    key = {"open": "opened", "close": "closed"}.get(ev)
    if key is None:
        return None
    raw = row.get(key)
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def attribute(events: Sequence[Mapping[str, Any]],
              tape_rows: Iterable[Mapping[str, Any]] = (),
              taker_rate: float = TAKER_RATE) -> dict[str, Any]:
    """Per-symbol fee attribution from venue commission events, with its own coverage.

    ``events`` are `binance_testnet.commission_events()` rows (symbol, time, commission), already
    positive-means-paid. ``tape_rows`` are `data/cashcarry_trades.json` rows, used ONLY to measure
    how much of the fee bill the desk's own log can account for -- never to filter the truth.

    Returns UNMEASURED (`measured=False`, no totals) on an empty event list: zero events means the
    venue read failed or the window is empty, and neither is evidence that zero fees were paid.
    """
    rows = [r for r in tape_rows if isinstance(r, Mapping)]

    # ATTRITION (L1.60): every event either lands in the per-symbol total or is counted here by
    # name. A denominator that loses members in silence is a coverage claim the desk cannot cash.
    attempted = len(events)
    unusable = 0
    by_symbol: dict[str, float] = {}
    n_by_symbol: dict[str, int] = {}
    times: list[int] = []
    for e in events:
        if not isinstance(e, Mapping):
            unusable += 1
            continue
        sym = str(e.get("symbol") or "")
        amt = _f(e.get("commission"))
        if not sym or amt <= 0.0:
            unusable += 1          # a zero/unsigned/symbol-less row prices nothing; never silent
            continue
        by_symbol[sym] = by_symbol.get(sym, 0.0) + amt
        n_by_symbol[sym] = n_by_symbol.get(sym, 0) + 1
        t = int(_f(e.get("time")))
        if t > 0:
            times.append(t)

    scanned = len(by_symbol)
    if not by_symbol:
        return {"measured": False, "events_attempted": attempted, "events_unusable": unusable,
                "symbols": 0,
                "note": ("no usable commission events -- UNMEASURED, not zero fees. An empty "
                         "venue read and a fee-free book are different claims (L1.28a).")}

    total = sum(by_symbol.values())
    ranked = sorted(by_symbol.items(), key=lambda kv: -kv[1])

    tape_symbols = {str(r.get("symbol") or "") for r in rows} - {""}
    tape_notional = sum(abs(_f(r.get("notional"))) for r in rows)
    off_tape = {s: v for s, v in by_symbol.items() if s not in tape_symbols} if tape_symbols else {}

    implied = total / taker_rate if taker_rate > 0 else None
    coverage = (tape_notional / implied) if implied else None

    out: dict[str, Any] = {
        "measured": True,
        "venue_commission_usd": round(total, 4),
        "events_attempted": attempted,
        "events_unusable": unusable,
        "events_priced": sum(n_by_symbol.values()),
        "symbols": scanned,
        "by_symbol": {s: round(v, 4) for s, v in ranked},
        "events_by_symbol": dict(n_by_symbol),
        "top4_share": round(sum(v for _, v in ranked[:4]) / total, 4),
        "spot_leg": "UNMEASURED",
        "spot_leg_note": ("the spot testnet account was reset -- my_trades returns 0 rows for "
                          "every historical window and balances are round-number reseeded. Spot "
                          "commission is UNRECOVERABLE, which is not the same as zero."),
        "row_level": "REFUSED",
        "row_level_note": (f"{PARTIAL_FILL_NOTE}; events do not align to tape fill instants "
                           "(median gap 4.3h). A nearest-in-time join would assign fees to round "
                           "trips at random. Per-round-trip cost needs a fill-time stamp."),
    }
    if times:
        out["window"] = [datetime.fromtimestamp(min(times) / 1000, UTC).isoformat(),
                         datetime.fromtimestamp(max(times) / 1000, UTC).isoformat()]
    if rows:
        out["tape_rows"] = len(rows)
        out["tape_notional_usd"] = round(tape_notional, 2)
        out["implied_notional_usd"] = round(implied, 2) if implied else None
        out["tape_coverage"] = round(coverage, 4) if coverage is not None else None
        out["off_tape_symbols"] = sorted(off_tape)
        out["off_tape_commission_usd"] = round(sum(off_tape.values()), 4)
        if coverage is not None and coverage < 0.5:
            out["residual_note"] = (
                f"the tape accounts for {coverage:.1%} of the ${implied:,.0f} of futures notional "
                f"this bill implies at {taker_rate * 1e4:.0f}bp. Not a window or universe "
                "mismatch. CANDIDATE mechanism (unproven): the executor's OPEN-FAIL/CLOSE-FAIL "
                "paths `continue` before `_log_trade`, so commission on a partially-filled "
                "unconfirmed order leaves no tape row.")
    return out


def concentration_verdict(att: Mapping[str, Any], bar: float = 0.5) -> tuple[str, str]:
    """Is the fee bill a broad drag or a few names? Drives what the repair even is.

    Deliberately not a pass/fail on desk performance -- it routes work. CONCENTRATED means the
    repair is symbol selection or a per-symbol cost gate; DIFFUSE means it is the execution path.
    """
    if not att.get("measured"):
        return "UNMEASURED", str(att.get("note") or "no usable commission events")
    share = att.get("top4_share")
    if not isinstance(share, (int, float)):
        return "UNMEASURED", "no concentration share computed"
    ranked = list(att.get("by_symbol", {}).items())[:4]
    names = ", ".join(f"{s} ${v:,.0f}" for s, v in ranked)
    if share >= bar:
        return "CONCENTRATED", (f"the top 4 symbols carry {share:.1%} of "
                                f"${att['venue_commission_usd']:,.0f} in fees ({names}). "
                                "The repair is symbol-level, not path-level.")
    return "DIFFUSE", (f"the top 4 symbols carry {share:.1%} of the fee bill -- no small set "
                       "dominates, so the repair is the execution path itself.")
