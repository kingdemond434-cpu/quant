"""R0371: attribute the sleeve's fee bill to symbols, from venue truth.

WHY THIS ORGAN EXISTS. `web/cashcarry_live.json` says $1,750.88 of futures commission is 88.7% of
the sleeve's entire non-funding loss, and the desk could not say which symbol paid it: 0 of 500
rows in the trade tape carry a fee field. `binance_testnet.commission_events()` could answer it
and had ZERO CALLERS repo-wide -- built, audited, paginated, and wired to nothing. This is the
consumer. The arithmetic lives in `libs.research.fee_attribution` and is pure; this script is the
venue read, the artifact write, and nothing else.

READ-ONLY AND KEYED. Signed GETs against the futures income ledger (`/fapi/v1/income`,
incomeType=COMMISSION) through the audited `_income_rows` pagination -- the only sanctioned path
(the 2026-07-26 truncation incident: a direct limit=1000 call understated commission by ~4.4x).
It places no orders and touches no money-path module.

REFUSAL PATH (L1.41). A failed or empty venue read publishes `measured: false` and no totals. An
empty read and a fee-free book are different claims, and only one of them is evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.input_provenance import Inputs  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.fee_attribution import attribute, concentration_verdict  # noqa: E402

_OUT = _ROOT / "data" / "fee_attribution.json"
_TAPE = "data/cashcarry_trades.json"

#: The sleeve's whole trading history is inside this. Wider than needed on purpose: the income
#: endpoint is paginated, so an over-wide window costs pages, while a too-narrow one silently
#: understates the bill -- the failure that is invisible in the output.
_LOOKBACK_DAYS = 90


def _fetch(since_ms: int) -> tuple[list[dict[str, Any]], str | None]:
    """Venue commission events, or ([], reason). Never raises into the caller's verdict."""
    try:
        from libs.execution import binance_testnet as fut
    except Exception as e:                       # an import failure is a real state
        return [], f"connector import failed: {e!r}"
    try:
        return list(fut.commission_events(since_ms)), None
    except Exception as e:                       # a venue/auth failure is a real state
        return [], f"venue read failed: {e!r}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true",
                    help="prove the arithmetic offline, with no keys and no network")
    ap.add_argument("--days", type=int, default=_LOOKBACK_DAYS)
    args = ap.parse_args()

    _law_guard()

    if args.self_test:
        att = attribute([{"symbol": "COOKIEUSDT", "commission": 623.30, "time": 1},
                         {"symbol": "1000CATUSDT", "commission": 413.03, "time": 2},
                         {"symbol": "MOVEUSDT", "commission": 245.95, "time": 3},
                         {"symbol": "TSTUSDT", "commission": 221.54, "time": 4},
                         {"symbol": "GTCUSDT", "commission": 19.83, "time": 5}])
        v, why = concentration_verdict(att)
        print("=== FEE ATTRIBUTION (self-test) ===")
        print(f"  commission ${att['venue_commission_usd']:,.2f} over {att['symbols']} symbols")
        print(f"  VERDICT: {v} -- {why}")
        return 0

    inp = Inputs(caller="run_fee_attribution.main")
    tape = inp.read_json(_TAPE, default=[], required=False)
    rows = tape if isinstance(tape, list) else []

    since = int((datetime.now(tz=UTC) - timedelta(days=args.days)).timestamp() * 1000)
    events, err = _fetch(since)
    if err:
        inp.defaulted("binance_testnet.commission_events", err)

    att = attribute(events, rows)
    v, why = concentration_verdict(att)

    print("=== FEE ATTRIBUTION (venue truth) ===")
    if not att.get("measured"):
        print(f"  UNMEASURED -- {err or att.get('note')}")
    else:
        print(f"  commission ${att['venue_commission_usd']:,.2f} over {att['symbols']} symbols "
              f"from {att['events_priced']:,} events")
        for sym, amt in list(att["by_symbol"].items())[:4]:
            print(f"     {sym:<14} ${amt:>9,.2f}")
        cov = att.get("tape_coverage")
        if cov is not None:
            print(f"  tape coverage {cov:.1%} of ${att['implied_notional_usd']:,.0f} implied "
                  f"notional -- the tape cannot see the rest")
        print(f"  spot leg: {att['spot_leg']} | per-round-trip: {att['row_level']}")
    print(f"  VERDICT: {v} -- {why}")

    payload = {"ran": datetime.now(tz=UTC).isoformat(), "verdict": v, "why": why,
               "lookback_days": args.days, "attribution": att,
               "provenance": inp.block(), "provenance_status": inp.status(),
               "provenance_why": inp.why(),
               # The venue read is the binding input: a clean tape cannot make an absent
               # commission feed measurable, so the artifact's own flag is the attribution's.
               "measured": bool(att.get("measured"))}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"  -> {_OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
