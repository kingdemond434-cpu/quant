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
  maker_rate        share of fills that were maker
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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
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

    THIS IS THE GUARD, NOT THE FIX (R0324, due 2026-08-02). Teaching `_is_maker` to read
    `spot_mode`/`fut_mode` is the real repair, and it is deliberately NOT done here because those
    rows carry TWO legs each ('maker' / 'taker' / 'taker_fallback' / 'already-flat') against a
    one-verdict-per-row reader, and `already-flat` is not a fill at all so it must not enter the
    denominator. Getting that wrong yields a plausible WRONG rate, which is worse than an obvious
    refusal: an implausible 0% gets investigated, a believable 43% gets believed.
    """
    return any(k in r for r in rows for k in _LIQUIDITY_FIELDS)


def _fee(r: dict) -> float:
    for k in ("fee", "commission", "fee_usd"):
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
    makers = [r for r in rows if _is_maker(r)]
    takers = [r for r in rows if not _is_maker(r)]
    fee_all = sum(_fee(r) for r in rows)
    fee_taker = sum(_fee(r) for r in takers)
    notional = sum(_notional(r) for r in rows)
    return {
        "fills": n,
        "maker_fills": len(makers),
        "maker_rate": round(len(makers) / n, 4),
        "fees_usd": round(fee_all, 4),
        # The 96.5% statistic: what share of all fees the taker MINORITY is responsible for.
        "fee_concentration": round(fee_taker / fee_all, 4) if fee_all > 0 else None,
        "taker_share_of_fills": round(len(takers) / n, 4),
        # One-way bps; x2 for a round trip, which is the unit the growth ladder prices.
        "bps_per_rt": round((fee_all / notional) * 1e4 * 2, 3) if notional > 0 else None,
    }


def verdict(now: dict, prior: dict | None) -> tuple[str, str]:
    rate = now.get("maker_rate")
    if rate is None:
        return "NO DATA", "no fills recorded -- the loop cannot answer whether the fix works"
    if rate >= TARGET_MAKER_RATE:
        return "PASS", f"maker rate {rate:.1%} >= target {TARGET_MAKER_RATE:.0%}"
    prev = (prior or {}).get("maker_rate")
    if prev is None:
        return "BASELINE", f"maker rate {rate:.1%} recorded; trend needs a second measurement"
    delta = rate - prev
    if delta > 0.02:
        return "IMPROVING", (f"maker rate {rate:.1%} (+{delta:.1%}) but below "
                             f"{TARGET_MAKER_RATE:.0%}")
    return "STALLED", (f"maker rate {rate:.1%} ({delta:+.1%}) -- patient-opens shipped "
                       f"{FIX_SHIPPED} and the rate is not climbing. An accepted fix that did "
                       "not move its own metric is a DEFECT, not a note.")


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
