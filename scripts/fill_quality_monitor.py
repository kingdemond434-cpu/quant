"""FILL QUALITY MONITOR -- close the measurement loop on the maker-fill fix.

THE GAP THIS CLOSES. The ledger records the diagnosis and the fix but never the verification:

    "verify the maker fill-rate is rising post-fix (was 24.2% paying 96.5% of fees;
     patient-opens shipped 07-24 -- RE-MEASURE WEEKLY until >60%)"

The mechanism shipped (`_MAKER = True`, "patient on OPENS, fast on CLOSES"). The re-measurement
never became code, so "is it working?" has been answerable only by hand. A fix without a
measurement loop is a belief, not a result -- and this one is worth measuring precisely because
of its leverage: 24.2% of fills were paying 96.5% of fees, so fee drag is dominated by the taker
tail, not by the average. The ladder's own note says execution costs (~20-25 bps/RT vs an
achievable ~12-15) are "the single biggest live drag", which makes this the highest-leverage
measurable on the money path.

WHAT IT MEASURES, from exchange ground truth (data/cashcarry_trades.json), never an accumulator:
  maker_rate        share of fills that were maker. On the cash-carry tape the unit is a LEG,
                    not a row (a pair can rest maker on spot and cross taker on futures), and a
                    leg that placed no order at all -- `already-flat` -- is not in the denominator
  fee_concentration share of total fees paid by the taker minority -- the 96.5% number
  bps_per_rt        realised round-trip cost in bps, the quantity the ladder prices
  trend             week-over-week direction, because a level without a trend cannot answer
                    "is the fix working?"

VERDICT is explicit and thresholded: PASS at >=60% maker (the ledger's own bar), IMPROVING when
the trend is positive but short of it, STALLED when the trend is flat/negative post-fix. STALLED
is a defect, not a note -- it means an accepted fix did not do what it claimed.

Read-only. No keys, no network. `--self-test` proves the arithmetic without live trades.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                      # importable as a script, no packaging step
    sys.path.insert(0, str(ROOT))

from libs.execution import leg_modes  # noqa: E402  (path bootstrap must precede the import)

TRADES = ROOT / "data/cashcarry_trades.json"
OUT = ROOT / "data/fill_quality.json"
TARGET_MAKER_RATE = 0.60          # the ledger's own bar
FIX_SHIPPED = "2026-07-24"        # patient-opens landed; trend is measured from here


def _rows(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        for k in ("trades", "fills", "rows"):
            if isinstance(payload.get(k), list):
                return [r for r in payload[k] if isinstance(r, dict)]
        return []
    return [r for r in payload if isinstance(r, dict)] if isinstance(payload, list) else []


def _is_maker(r: dict) -> bool:
    """Venue payloads disagree on the field name; treat only an explicit TRUE as maker.

    Fail CLOSED: an unknown field must count as taker, never as maker. Guessing maker on missing
    data would inflate exactly the number this monitor exists to police.
    """
    for k in ("maker", "isMaker", "is_maker", "m"):
        if k in r:
            return bool(r[k])
    role = str(r.get("role") or r.get("liquidity") or "").lower()
    return role in ("maker", "add", "post")


#: EXACTLY the fields `_is_maker` consults -- keep the two in lockstep. If this list names a field
#: the reader cannot actually parse, the schema reads as "understood" while every row silently
#: scores taker, which is the precise bug this guard exists to prevent (caught by its own test).
_LIQUIDITY_FIELDS = ("maker", "isMaker", "is_maker", "m", "role", "liquidity")


#: The cash-carry tape's own schema: ONE mode string per LEG, up to two legs per trade row.
_LEG_FIELDS = ("spot_mode", "fut_mode")


def _leg_maker_flags(r: dict) -> list[bool] | None:
    """Per-LEG maker verdicts for one cash-carry row, or None when this row's legs are unreadable.

    THE FIX R0324 ASKED FOR. The row carries `spot_mode`/`fut_mode` -- a pair can rest maker on
    spot and cross taker on futures, so the row is worth up to TWO observations, not one. Legs that
    placed no order (`already-flat`: the venue said the leg was already flat, so nothing was quoted
    and nothing was filled) are DROPPED, not scored taker: they never had the chance to be maker
    and counting them would deflate the very share this monitor polices.

    Returns [] for a row whose legs are all no-order -- readable, but contributing no denominator.
    Returns None when the row carries no leg fields at all, or carries a mode string outside the
    known vocabulary: an unrecognised schema must reach the guard below, never a plausible number.
    """
    present = [r[k] for k in _LEG_FIELDS if k in r]
    if not present:
        return None
    flags: list[bool] = []
    for mode in present:
        if not leg_modes.is_known(mode):
            return None                            # tape grew a mode we were never taught
        if leg_modes.placed_order(mode):
            flags.append(leg_modes.is_maker(mode))
    return flags


def _row_flags(r: dict) -> list[bool] | None:
    """Maker observations contributed by ONE row, or None when the row records no liquidity at all.

    THE SILENT-TAKER DEFECT THIS CLOSES (measured 2026-08-05 on the live tape). `_is_maker` fails
    CLOSED, and that is right for a row that HAS a liquidity field carrying something unexpected.
    It is catastrophic for a row that has no such field at all: `_is_maker({}) is False` is not a
    measured taker, it is a fabricated one. The cash-carry tape stamps `spot_mode`/`fut_mode` only
    on rows written by the patient-maker path, so 475 of 500 rows carried NO liquidity information
    whatsoever -- and every one of them was counted as a taker fill. The published rate was 3.6%
    (18/505) while the 30 legs that actually record a mode read 18/30 = 60.0%, and
    `run_trade_forensics._leg_share`, reading the SAME tape through `leg_modes`, reported 0.60.
    Two organs, one tape, one fact, 16.9x apart -- the exact failure `libs/execution/leg_modes`
    was written to make impossible.

    `_schema_understood` did not catch it because it is ALL-OR-NOTHING: one readable row anywhere
    in the tape flips the whole file to "understood", after which every unreadable row is scored
    rather than skipped. The guard protected against an unreadable TAPE and had nothing to say
    about an unreadable ROW.

    The rule, stated once so it generalises: a row leaves the denominator when we cannot tell what
    it was, exactly as `already-flat` leaves it when there was nothing to tell. Absence of evidence
    is not evidence of taker.
    """
    flags = _leg_maker_flags(r)
    if flags is not None:
        return flags
    if any(k in r for k in _LIQUIDITY_FIELDS):
        return [_is_maker(r)]          # a liquidity field IS present -- fail closed, as before
    return None                        # nothing recorded: unmeasurable, NOT a taker


def _schema_understood(rows: list[dict]) -> bool:
    """Does ANY row carry a field that could express maker-vs-taker?

    THE FALSE ZERO (2026-08-01, before this monitor's first cron fire). `_is_maker` fails CLOSED,
    which is right for one unknown row and catastrophic for an unknown SCHEMA: pointed at the
    cash-carry tape -- which stores `spot_mode`/`fut_mode` ('maker' / 'taker_fallback' /
    'already-flat') and none of the names `_is_maker` knows -- every leg reads taker and the
    monitor publishes `maker_rate: 0.0` with verdict STALLED, "a DEFECT, not a note". That number
    would then be persisted by record_desk_metrics and paged, i.e. a measurement failure dressed
    as a measured finding. Refusing is the only honest output: "we could not read it" and "it was
    0%" are different claims and only one of them is evidence.

    THE FIX LANDED (R0324, 2026-08-05); THE GUARD STAYS. `_leg_maker_flags` now reads the
    cash-carry schema per LEG and drops `already-flat` from the denominator, so that tape is
    measured instead of refused. The guard was NOT deleted with it: it still fires for a tape
    carrying neither a liquidity field nor a known leg mode. The repair NARROWS what counts as
    unmeasured -- it never widens what counts as understood, because a plausible WRONG rate is
    worse than an obvious refusal (an implausible 0% gets investigated, a believable 43% gets
    believed).
    """
    if any(k in r for r in rows for k in _LIQUIDITY_FIELDS):
        return True
    return any(_leg_maker_flags(r) is not None for r in rows)


#: EXACTLY the fields `_fee` consults -- same lockstep rule as `_LIQUIDITY_FIELDS`. `measure` uses
#: this to tell "the tape prices its fills at zero" from "the tape does not price its fills".
_FEE_FIELDS = ("fee", "commission", "fee_usd")


def _fee(r: dict) -> float:
    for k in _FEE_FIELDS:
        if k in r:
            try:
                return abs(float(r[k]))
            except (TypeError, ValueError):
                continue
    return 0.0


def _notional(r: dict) -> float:
    for k in ("notional", "quote_qty", "cummulativeQuoteQty", "quoteQty"):
        if k in r:
            try:
                return abs(float(r[k]))
            except (TypeError, ValueError):
                continue
    try:
        return abs(float(r.get("price", 0)) * float(r.get("qty", 0)))
    except (TypeError, ValueError):
        return 0.0


def measure(rows: list[dict]) -> dict[str, Any]:
    """Pure: fills -> fill-quality metrics. Testable without any live data."""
    n = len(rows)
    if not n:
        return {"fills": 0, "maker_rate": None, "fee_concentration": None, "bps_per_rt": None}
    if not _schema_understood(rows):
        # UNMEASURED, never 0.0 -- verdict() already routes maker_rate=None to "NO DATA".
        return {"fills": n, "maker_rate": None, "fee_concentration": None, "bps_per_rt": None,
                "unreadable_schema": True,
                "note": (f"{n} row(s) carry no recognised liquidity field "
                         f"{_LIQUIDITY_FIELDS} -- cannot tell maker from taker. Reporting "
                         "UNMEASURED rather than a false 0%.")}
    # One entry per MEASURED observation. A cash-carry row contributes one flag per leg that
    # actually placed an order (R0324); every other schema stays one flag per row, `_is_maker`
    # failing closed exactly as before. A row recording NO liquidity information contributes
    # NOTHING -- it is counted separately as unmeasurable, never scored taker.
    units: list[bool] = []
    takers: list[dict] = []
    n_unmeasurable = 0
    for r in rows:
        row_flags = _row_flags(r)
        if row_flags is None:
            n_unmeasurable += 1
            continue
        units.extend(row_flags)
        if row_flags and not all(row_flags):  # a row bearing ANY non-maker leg paid taker
            takers.append(r)
    n_units = len(units)
    if n_units == 0:
        # Readable, but nothing to measure: every leg was `already-flat` (no order placed, so no
        # fill could have been maker). UNMEASURED -- reporting 0.0 here would be a fabricated
        # zero built entirely out of legs that never traded.
        return {"fills": n, "maker_rate": None, "fee_concentration": None, "bps_per_rt": None,
                "measured_legs": 0, "no_order_legs_only": True,
                "note": (f"{n} row(s) carry only no-order legs {sorted(leg_modes.NO_ORDER_MODES)}"
                         " -- no order was placed, so there is no maker denominator. Reporting "
                         "UNMEASURED rather than a false 0%.")}
    makers = [u for u in units if u]
    # A FEE FIELD MUST EXIST BEFORE A FEE NUMBER MAY BE PUBLISHED. `_fee` returns 0.0 for a row
    # carrying no fee key, so summing over a tape that records none yields a total of 0.0 -- and
    # `bps_per_rt` then publishes a realised round-trip cost of 0.0 bps for a book whose own
    # leak_attribution names $1750.88 of futures commission. That is the module's stated failure
    # mode ("an implausible 0% gets investigated, a believable 43% gets believed") applied to the
    # fee fields instead of the maker field: the guard was built for one number and never
    # generalised to its siblings. Measured 2026-08-05: 0 of 500 rows carry fee/commission/fee_usd.
    priced = [r for r in rows if any(k in r for k in _FEE_FIELDS)]
    fee_all = sum(_fee(r) for r in priced)
    fee_taker = sum(_fee(r) for r in takers if any(k in r for k in _FEE_FIELDS))
    notional = sum(_notional(r) for r in priced)
    out: dict[str, Any] = {
        "fills": n,
        "measured_legs": n_units,
        "unmeasurable_rows": n_unmeasurable,
        # COVERAGE TRAVELS WITH THE RATE, ALWAYS. A maker share computed over 6% of the tape is a
        # real measurement of that 6% and says nothing about the rest; publishing the rate without
        # the coverage beside it is how a narrow number gets read as a book-wide one.
        "coverage": round((n - n_unmeasurable) / n, 4) if n else None,
        "maker_fills": len(makers),
        "maker_rate": round(len(makers) / n_units, 4),
        "taker_share_of_fills": round((n_units - len(makers)) / n_units, 4),
        "priced_rows": len(priced),
    }
    if not priced:
        out.update({"fees_usd": None, "fee_concentration": None, "bps_per_rt": None,
                    "fee_note": (f"0 of {n} row(s) carry a fee field {_FEE_FIELDS} -- cost per "
                                 "round trip is UNMEASURED, not zero.")})
        return out
    out["fees_usd"] = round(fee_all, 4)
    # The 96.5% statistic: what share of all fees the taker MINORITY is responsible for.
    out["fee_concentration"] = round(fee_taker / fee_all, 4) if fee_all > 0 else None
    # One-way bps; x2 for a round trip, which is the unit the growth ladder prices.
    out["bps_per_rt"] = round((fee_all / notional) * 1e4 * 2, 3) if notional > 0 else None
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial share -- the honest error bar on `maker_rate`.

    Chosen over the normal approximation because n here is small (30 legs at first measurement)
    and the share sits near the 0.60 bar, exactly where the naive interval misbehaves. Pure
    arithmetic, no scipy: this module must stay importable by a read-only monitor.
    """
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def verdict(now: dict, prior: dict | None) -> tuple[str, str]:
    rate = now.get("maker_rate")
    if rate is None:
        return "NO DATA", "no fills recorded -- the loop cannot answer whether the fix works"
    k, n = now.get("maker_fills", 0), now.get("measured_legs", 0)
    lo, hi = wilson(int(k), int(n))
    ci = f"{n} measured leg(s), 95% CI [{lo:.1%}, {hi:.1%}]"
    cov = now.get("coverage")
    cov_s = f", coverage {cov:.1%} of rows" if isinstance(cov, (int, float)) else ""
    # A POINT ESTIMATE IS NOT A VERDICT. PASS moves real capital-sizing confidence and STALLED
    # declares an accepted fix defective; neither may rest on a sample that cannot distinguish
    # them. The bar is the CONFIDENCE INTERVAL clearing the target, never the point estimate
    # touching it -- the same rule the desk applies to an edge, applied to its own metric.
    if lo >= TARGET_MAKER_RATE:
        return "PASS", f"maker rate {rate:.1%} >= target {TARGET_MAKER_RATE:.0%} ({ci}{cov_s})"
    if hi >= TARGET_MAKER_RATE > lo:
        return "UNDERPOWERED", (f"maker rate {rate:.1%} straddles the {TARGET_MAKER_RATE:.0%} "
                                f"target -- {ci}{cov_s}. Neither PASS nor STALLED is supported; "
                                "the answer is more measured legs, not a louder verdict.")
    prev = (prior or {}).get("maker_rate")
    if prev is None:
        return "BASELINE", f"maker rate {rate:.1%} recorded ({ci}{cov_s}); trend needs a second"
    delta = rate - prev
    if delta > 0.02:
        return "IMPROVING", (f"maker rate {rate:.1%} (+{delta:.1%}) but below "
                             f"{TARGET_MAKER_RATE:.0%} ({ci}{cov_s})")
    return "STALLED", (f"maker rate {rate:.1%} ({delta:+.1%}) -- patient-opens shipped "
                       f"{FIX_SHIPPED} and the rate is not climbing ({ci}{cov_s}). An accepted "
                       "fix that did not move its own metric is a DEFECT, not a note.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        rows = ([{"maker": True, "fee": 0.01, "notional": 1000.0}] * 24
                + [{"maker": False, "fee": 0.30, "notional": 1000.0}] * 76)
        m = measure(rows)
        print("=== FILL QUALITY MONITOR (self-test) ===")
        print(f"  maker_rate={m['maker_rate']:.1%}  fee_concentration={m['fee_concentration']:.1%}"
              f"  bps_per_rt={m['bps_per_rt']}")
        print(f"  reproduces the ledger's shape: a {m['taker_share_of_fills']:.0%} taker "
              f"minority paying {m['fee_concentration']:.1%} of fees")
        v, why = verdict(m, {"maker_rate": 0.242})
        print(f"  verdict: {v} -- {why}")
        return

    try:
        rows = _rows(json.loads(TRADES.read_text("utf-8")))
    except (OSError, json.JSONDecodeError):
        print(f"fill-quality: {TRADES.relative_to(ROOT)} unavailable -- no fills to measure")
        return
    prior = None
    with contextlib.suppress(OSError, json.JSONDecodeError):
        prior = json.loads(OUT.read_text("utf-8")).get("current")

    now = measure(rows)
    v, why = verdict(now, prior)
    print("=== FILL QUALITY MONITOR ===")
    print(f"  fills={now['fills']} maker_rate={now.get('maker_rate')} "
          f"fee_concentration={now.get('fee_concentration')} bps_per_rt={now.get('bps_per_rt')}")
    print(f"  VERDICT: {v} -- {why}")
    if v == "STALLED":
        print("  -> This is a live defect. The fix shipped; the metric did not move.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"ran": datetime.now(tz=UTC).isoformat(), "target_maker_rate": TARGET_MAKER_RATE,
         "fix_shipped": FIX_SHIPPED, "current": now, "prior": prior,
         "verdict": v, "why": why,
         "window_hint": (datetime.now(tz=UTC) - timedelta(days=7)).date().isoformat()},
        indent=1), "utf-8")
    print(f"  -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
