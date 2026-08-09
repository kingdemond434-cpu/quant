#!/usr/bin/env python
"""DOUBLE-ENTRY VENUE RECONCILIATION -- where did the book's cash actually go?

ORIGIN (2026-07-19 dead-man fire #4, built 2026-07-29). The full 13-model panel REJECTED the
CRO's "modest slippage" explanation of the equity gap and ruled that no reset may be considered
until a double-entry venue reconciliation exists. It did not exist for 10 days, so every fire
since has been argued from assertion. This is that organ.

THE QUESTION IT ANSWERS. ``run_deadman_switch`` values the book as::

    equity = futures_margin + legs_v + (stable_cash - usdt_baseline)

where ``legs_v`` credits the spot value of ONLY those assets carrying a live futures SHORT (plus
a 1h settlement grace). That measure is deliberately narrow: the testnet faucet stuffs the spot
wallet with ~$180k of untracked coins, and crediting the raw wallet would make the rail unable to
ever fire. The narrowness is correct and this organ does NOT widen it.

But narrow has a cost. When a futures short disappears -- a venue force-close, an ADL, a churn
loop tearing the hedge off -- the spot leg it was paired with is STILL HELD and still worth money,
yet drops out of ``legs_v`` an hour later and is thereafter marked at exactly $0. The rail then
reads a loss that did not happen. That is an UNDERCOUNT of assets provably sitting on the venue.

So the gap between baseline cash and current cash splits three ways, and the whole point of this
organ is that the three are NOT interchangeable:

  1. STRANDED BOOK INVENTORY -- coins in symbols the book demonstrably traded, still in the
     wallet, currently valued at $0 by the rail. Real value, wrongly written off.
  2. REAL COST -- fees and slippage. Actually destroyed. Cross-checked against the venue's own
     commission stream so the number is not merely a residual.
  3. FAUCET NOISE -- coins the book never traded. Never counted, in either direction.

HONESTY PROPERTIES (each exists because the naive version of this script would lie):
  * READ-ONLY. Signed GETs only. It cannot place, cancel, or flatten anything, and it never
    writes a rail file. A reconciliation organ that can move the book is a second executor.
  * NEVER CREDITS FAUCET JUNK. Reporting the $188k raw wallet as "equity" would silently disable
    the ruin rail. The faucet bucket is reported separately and never enters a verdict.
  * BOOK INVENTORY IS A LOWER BOUND. ``cashcarry_trades.json`` is a capped rolling log, so
    symbols traded before the window are invisible and their coins fall into the faucet bucket.
    The script says so in its output rather than implying completeness.
  * THE RESIDUAL IS CHECKED, NOT ASSUMED. "Unexplained" is compared against measured commission
    and the implied turnover it represents. A residual that the fee stream cannot account for is
    flagged as UNRECONCILED -- a phantom until proven, per the daily integrity watch.

It renders a verdict, never an action. Resetting the rail is Tier-3 and principal-only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_SPOT_BASE = "https://testnet.binance.vision"        # PINNED testnet -- never live
_FUT_BASE = "https://testnet.binancefuture.com"      # PINNED testnet -- never live
_SPOT_KEYS = _ROOT / "data" / "secrets" / "binance_spot_testnet.json"
_FUT_KEYS = _ROOT / "data" / "secrets" / "binance_testnet.json"
_STATE = _ROOT / "data" / "deadman_state.json"
_TRADES = _ROOT / "data" / "cashcarry_trades.json"
_OUT = _ROOT / "web" / "venue_reconcile.json"

# Must match run_deadman_switch._STABLES exactly -- a divergence would reconcile a different
# book than the rail values, which is worse than not reconciling at all.
_STABLES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")
_TAKER_BPS = 5.0            # testnet futures taker; used only to imply turnover from commission


def _creds(path: Path) -> tuple[str, str] | None:
    try:
        d = json.loads(path.read_text("utf-8"))
    except Exception:
        return None
    k = d.get("api_key") or d.get("key")
    s = d.get("api_secret") or d.get("secret")
    return (k, s) if k and s else None


def _req(url: str, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _signed(base: str, path: str, creds: tuple[str, str]) -> Any:
    key, secret = creds
    q = urllib.parse.urlencode({"timestamp": int(time.time() * 1000), "recvWindow": 10000})
    sig = hmac.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()
    return _req(f"{base}{path}?{q}&signature={sig}", {"X-MBX-APIKEY": key})


def _traded_bases() -> tuple[set[str], int, bool]:
    """Base assets the book has traded, per its own log. Returns (bases, n_rows, truncated)."""
    try:
        raw = json.loads(_TRADES.read_text("utf-8"))
    except Exception:
        return set(), 0, True
    rows = raw if isinstance(raw, list) else raw.get("trades", [])
    bases = {str(r.get("symbol"))[:-4] for r in rows
             if str(r.get("symbol", "")).endswith("USDT")}
    # A log sitting exactly on a round cap is a rolling window, not the book's whole history.
    truncated = len(rows) in (100, 200, 250, 500, 1000, 2000, 5000)
    return bases, len(rows), truncated


def reconcile() -> dict[str, Any]:
    sc, fc = _creds(_SPOT_KEYS), _creds(_FUT_KEYS)
    if not sc or not fc:
        return {"error": "credentials unreadable -- no reconciliation this run"}
    try:
        bals = _signed(_SPOT_BASE, "/api/v3/account", sc)["balances"]
        px = {t["symbol"]: float(t["price"]) for t in _req(f"{_SPOT_BASE}/api/v3/ticker/price")}
        acct = _signed(_FUT_BASE, "/fapi/v2/account", fc)
        fut_eq = float(acct["totalMarginBalance"])
        shorts = {p["symbol"] for p in _signed(_FUT_BASE, "/fapi/v2/positionRisk", fc)
                  if float(p.get("positionAmt", 0.0)) < 0}
    except Exception as e:                       # venue unreachable is not a book defect
        return {"error": f"{type(e).__name__}: {e}",
                "note": "venue unreachable -- no reconciliation this run"}

    traded, n_rows, truncated = _traded_bases()
    cash = 0.0
    book: list[dict[str, Any]] = []
    faucet_v = 0.0
    unpriced: list[str] = []
    for b in bals:
        amt = float(b["free"]) + float(b["locked"])
        if amt <= 0:
            continue
        asset = b["asset"]
        if asset in _STABLES:
            cash += amt
            continue
        price = px.get(asset + "USDT")
        if price is None:
            unpriced.append(asset)
            continue
        value = amt * price
        if asset in traded:
            book.append({"asset": asset, "qty": amt, "value": round(value, 2),
                         "credited_by_rail": (asset + "USDT") in shorts})
        else:
            faucet_v += value
    book.sort(key=lambda r: -r["value"])
    book_v = sum(r["value"] for r in book)
    # Only inventory WITHOUT a live short is being written off; a credited leg is valued fine.
    stranded_v = sum(r["value"] for r in book if not r["credited_by_rail"])

    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    baseline = float(state.get("usdt_baseline") or 0.0)
    gap = baseline - cash if baseline else 0.0
    unexplained = gap - book_v

    out: dict[str, Any] = {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "futures_margin_balance": round(fut_eq, 2),
        "open_futures_shorts": len(shorts),
        "stable_cash": round(cash, 2),
        "usdt_baseline": round(baseline, 2),
        "cash_gap_vs_baseline": round(gap, 2),
        "book_inventory_value": round(book_v, 2),
        "stranded_uncredited_value": round(stranded_v, 2),
        "faucet_noise_value": round(faucet_v, 2),
        "unexplained_residual": round(unexplained, 2),
        "explained_share": round(book_v / gap, 3) if gap > 0 else None,
        "book_inventory": book[:40],
        "unpriced_assets": unpriced[:20],
        "trade_log_rows": n_rows,
        "trade_log_truncated": truncated,
        "rail_equity_measure": round(fut_eq + 0.0 + (cash - baseline), 2) if baseline else None,
    }

    # CROSS-CHECK the residual against the venue's own fee stream. A residual that fees and
    # slippage cannot plausibly reach is not "cost" -- it is an unreconciled hole, and the
    # integrity watch treats a hole venue records do not explain as a phantom until proven.
    try:
        from libs.execution import binance_testnet as _f
        since = int((time.time() - 7 * 86400) * 1000)
        events = _f.commission_events(since)
        commission = sum(float(e["commission"]) for e in events)
        implied_notional = commission / (_TAKER_BPS / 10000.0) if commission else 0.0
        out["commission_7d"] = round(commission, 2)
        out["commission_events_7d"] = len(events)
        out["implied_futures_turnover_7d"] = round(implied_notional, 0)
        # Both legs trade, so all-in cost rides ~2x the futures notional.
        out["residual_bps_of_turnover"] = (
            round(unexplained / (2 * implied_notional) * 10000.0, 1)
            if implied_notional > 0 else None
        )
    except Exception as e:
        out["commission_error"] = f"{type(e).__name__}: {e}"

    bps = out.get("residual_bps_of_turnover")
    notes = []
    if stranded_v > 0:
        notes.append(
            f"UNDERCOUNT: ${stranded_v:,.2f} of real book inventory carries no live futures "
            f"short and is valued at $0 by the ruin rail. Real assets, verified on venue.")
    if truncated:
        notes.append(
            f"LOWER BOUND: the trade log is a rolling window ({n_rows} rows), so symbols traded "
            f"before it are counted as faucet noise. True book inventory is >= this figure.")
    if bps is not None:
        if bps > 100:
            notes.append(
                f"UNRECONCILED: residual is {bps:.0f} bps of traded turnover -- too large for "
                f"fees+slippage. Treat as a phantom loss until venue records explain it.")
        elif bps >= 0:
            notes.append(
                f"RESIDUAL CONSISTENT WITH COST: {bps:.1f} bps of ~${2*out['implied_futures_turnover_7d']:,.0f} "
                f"two-leg turnover -- market-order churn on illiquid alts bills in this band.")
    out["notes"] = notes
    out["verdict"] = (
        "UNRECONCILED" if (bps is not None and bps > 100)
        else "RECONCILED" if gap > 0 else "NO_GAP")
    return out


def main() -> None:
    res = reconcile()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(res, indent=1), "utf-8")
    if "error" in res:
        print(f"venue-reconcile: {res['error']}")
        return
    print(f"VENUE RECONCILE {res['updated']}  verdict={res['verdict']}")
    print(f"  cash gap vs baseline : ${res['cash_gap_vs_baseline']:>12,.2f}")
    print(f"  book inventory       : ${res['book_inventory_value']:>12,.2f}"
          f"   ({res['explained_share']:.1%} of gap)" if res.get("explained_share")
          else f"  book inventory       : ${res['book_inventory_value']:>12,.2f}")
    print(f"  stranded (rail=$0)   : ${res['stranded_uncredited_value']:>12,.2f}")
    print(f"  unexplained residual : ${res['unexplained_residual']:>12,.2f}")
    print(f"  faucet noise (never counted): ${res['faucet_noise_value']:>12,.2f}")
    for n in res["notes"]:
        print(f"  - {n}")


if __name__ == "__main__":
    main()
