"""PRINCIPAL-APPROVED: flatten the inverted COOKIEUSDT futures LONG. reduceOnly, nothing else.

INCIDENT: COOKIEUSDT futures held +916,772 (LONG) where the carry requires -183,140 (SHORT).
Unrealized -$482.19 -- essentially the desk's entire loss -- with free margin down to $110.23 and
a liquidation price of 0.00516943. Cause: futures cover orders are not reduceOnly, so close/topup
retries bought through zero and flipped the short into a growing long.

SCOPE, DELIBERATELY MINIMAL AND APPROVED AS SUCH:
  * COOKIEUSDT FUTURES ONLY. Spot COOKIE (183,029) untouched. 1000CAT and MOVE shorts are
    CORRECTLY hedged and are not touched. TST is untouched.
  * reduceOnly=true so this order can only ever REDUCE toward zero. It is arithmetically
    incapable of repeating the bug it is cleaning up -- if the position is already flat or
    smaller than expected, the venue rejects or trims rather than opening a short.
  * Quantity read LIVE from positionRisk at execution time, never from a desk-written file.
    The desk's own state file is what was wrong here; trusting it would be the same error again.

Verifies before and after. Aborts if the position is not a long, or is not COOKIEUSDT.
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, ".")
import scripts.run_deadman_switch as D  # noqa: E402

SYM = "COOKIEUSDT"


def _market_max_qty(sym: str) -> float:
    """Venue's MARKET_LOT_SIZE cap, read live. Falls back to a conservative 100k."""
    try:
        info = D._req(f"{D._FUT_BASE}/fapi/v1/exchangeInfo")
        for s in info["symbols"]:
            if s["symbol"] == sym:
                for f in s["filters"]:
                    if f["filterType"] == "MARKET_LOT_SIZE":
                        return float(f["maxQty"])
    except Exception:  # noqa: BLE001
        pass
    return 100_000.0


def pos_amt(creds) -> float:
    for p in D._signed(D._FUT_BASE, "/fapi/v2/positionRisk", creds):
        if p.get("symbol") == SYM:
            return float(p.get("positionAmt", 0.0))
    return 0.0


def main() -> None:
    creds = D._creds(D._FUT_KEYS)
    if not creds:
        raise SystemExit("no futures credentials -- aborting")

    before = pos_amt(creds)
    print(f"BEFORE  {SYM} positionAmt = {before:+,.1f}")
    if before == 0:
        print("  already flat -- nothing to do"); return
    if before < 0:
        raise SystemExit(f"position is SHORT ({before:+,.1f}) -- that is the CORRECT direction "
                         f"for a carry. Refusing to touch it; this script only unwinds the "
                         f"inverted LONG it was written for.")

    # MARKET_LOT_SIZE maxQty = 150,000 on COOKIEUSDT. A single 916,772 order is rejected -4005
    # "Quantity greater than max quantity" -- AND THAT IS THE ROOT CAUSE OF THE INCIDENT ITSELF:
    # the executor's oversized market orders were rejected, _mkt_or_limit fell back to RESTING
    # post-only limits, and repeated cycles accumulated fills that walked the short through zero
    # into a long. Chunking is therefore not a workaround, it is the correct behaviour.
    max_qty = _market_max_qty(SYM)
    print(f"  MARKET_LOT_SIZE maxQty = {max_qty:,.0f} -> chunking")
    remaining = abs(before)
    n = 0
    while remaining > 0 and n < 20:
        cur = pos_amt(creds)
        if cur <= 0:
            print(f"  position reached {cur:+,.1f} -- stopping (reduceOnly cannot go short)")
            break
        chunk = min(max_qty, abs(cur))
        n += 1
        print(f"  [{n}] reduceOnly MARKET SELL {chunk:,.0f}  (position now {cur:+,.1f})")
        try:
            D._signed(D._FUT_BASE, "/fapi/v1/order", creds,
                      {"symbol": SYM, "side": "SELL", "type": "MARKET",
                       "quantity": chunk, "reduceOnly": "true"}, method="POST")
        except Exception as e:  # noqa: BLE001
            print(f"      CHUNK FAILED: {e!r} -- stopping. Position left at {pos_amt(creds):+,.1f}")
            print("      Not retrying blindly; blind retries created this incident.")
            break
        time.sleep(2)
        remaining = abs(pos_amt(creds))

    time.sleep(3)
    after = pos_amt(creds)
    print(f"AFTER   {SYM} positionAmt = {after:+,.1f}")
    acct = D._signed(D._FUT_BASE, "/fapi/v2/account", creds)
    print(f"  margin_balance={float(acct['totalMarginBalance']):.2f}  "
          f"available={float(acct['availableBalance']):.2f}  "
          f"unrealized={float(acct['totalUnrealizedProfit']):.2f}")
    print("\n  REMAINING venue futures positions:")
    for p in D._signed(D._FUT_BASE, "/fapi/v2/positionRisk", creds):
        a = float(p.get("positionAmt", 0.0))
        if a:
            print(f"    {p['symbol']:<14} {a:+15,.1f}  unrl {float(p['unRealizedProfit']):+9.2f}")
    print("\n  Spot COOKIE is deliberately still held; only the inverted futures leg was unwound.")


if __name__ == "__main__":
    main()
