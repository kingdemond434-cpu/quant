#!/usr/bin/env python3
"""READ-ONLY venue reconciliation for the 2026-07-19 dead-man fire (GAP #34).

Answers ONE question with venue ground truth: is the ~$1,838 USDT delta (and the
$785-vs-$2,409 equity discrepancy) a REAL loss, or a measurement artifact of
combined_equity()'s documented leg/cash race?

Method: replicate the dead-man's OWN formula component-by-component from fresh signed
reads, then attribute the USDT delta to futures income records (realized PnL, funding,
commission) and to spot coin holdings (USDT converted to coins is NOT a loss).

Touches nothing. Writes nothing. Imports nothing from the Tier-3 rail.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

ROOT = Path("/home/quant/quant-platform")
FUT_BASE = "https://testnet.binancefuture.com"
SPOT_BASE = "https://testnet.binance.vision"
FUT_KEYS = ROOT / "data/secrets/binance_testnet.json"
SPOT_KEYS = ROOT / "data/secrets/binance_spot_testnet.json"
STATE = ROOT / "data/deadman_state.json"
CTX = ssl.create_default_context(cafile=certifi.where())


def creds(p: Path):
    d = json.loads(p.read_text())
    return d.get("api_key") or d.get("key"), d.get("api_secret") or d.get("secret")


def req(url: str, key: str | None = None):
    r = urllib.request.Request(url, headers={"X-MBX-APIKEY": key} if key else {})
    with urllib.request.urlopen(r, timeout=20, context=CTX) as resp:
        return json.loads(resp.read())


def signed(base: str, path: str, c, params: dict | None = None):
    k, s = c
    p = dict(params or {})
    p["timestamp"] = int(time.time() * 1000)
    p["recvWindow"] = 20000
    q = urllib.parse.urlencode(p)
    sig = hmac.new(s.encode(), q.encode(), hashlib.sha256).hexdigest()
    return req(f"{base}{path}?{q}&signature={sig}", k)


def main() -> None:
    state = json.loads(STATE.read_text())
    baseline = float(state["usdt_baseline"])
    hw = float(state["high_water"])
    fired_eq = float(state["last_eq"])

    fut, spt = creds(FUT_KEYS), creds(SPOT_KEYS)
    acct = signed(FUT_BASE, "/fapi/v2/account", fut)
    fut_eq = float(acct["totalMarginBalance"])
    unreal = float(acct.get("totalUnrealizedProfit", 0))
    positions = [p for p in signed(FUT_BASE, "/fapi/v2/positionRisk", fut)
                 if abs(float(p.get("positionAmt", 0))) > 0]
    shorts = {p["symbol"] for p in positions if float(p["positionAmt"]) < 0}

    bals = signed(SPOT_BASE, "/api/v3/account", spt)["balances"]
    px = {t["symbol"]: float(t["price"]) for t in req(f"{SPOT_BASE}/api/v3/ticker/price")}
    usdt = 0.0
    legs_v = 0.0
    coins = []
    for b in bals:
        amt = float(b["free"]) + float(b["locked"])
        if amt <= 0:
            continue
        if b["asset"] == "USDT":
            usdt = amt
            continue
        val = amt * px.get(b["asset"] + "USDT", 0.0)
        coins.append((b["asset"], amt, val))
        if b["asset"] + "USDT" in shorts:
            legs_v += val
    coins.sort(key=lambda x: -x[2])
    coins_total = sum(c[2] for c in coins)

    equity_now = fut_eq + legs_v + (usdt - baseline)
    usdt_delta = usdt - baseline

    # Futures income attribution since the incident window (7 days back, paginated)
    since = int((time.time() - 7 * 86400) * 1000)
    income: dict[str, float] = {}
    rows = 0
    start = since
    for _ in range(20):
        batch = signed(FUT_BASE, "/fapi/v1/income", fut,
                       {"startTime": start, "limit": 1000})
        if not batch:
            break
        for r in batch:
            income[r["incomeType"]] = income.get(r["incomeType"], 0.0) + float(r["income"])
        rows += len(batch)
        if len(batch) < 1000:
            break
        start = int(batch[-1]["time"]) + 1

    print("=" * 72)
    print("VENUE RECONCILIATION -- dead-man fire 2026-07-19T14:27:56Z (READ-ONLY)")
    print("=" * 72)
    print("  formula: equity = fut_eq + legs_v + (usdt - usdt_baseline)")
    print(f"  high_water at fire      : ${hw:>12,.2f}")
    print(f"  equity AT FIRE (latched): ${fired_eq:>12,.2f}   <- 5 consecutive polls")
    print(f"  fire line (65% of HW)   : ${hw * 0.65:>12,.2f}")
    print("-" * 72)
    print("COMPONENTS NOW (fresh signed reads):")
    print(f"  futures totalMarginBalance : ${fut_eq:>12,.2f}")
    print(f"  futures unrealized PnL     : ${unreal:>12,.2f}")
    print(f"  open futures positions     : {len(positions)} (shorts: {len(shorts)})")
    print(f"  spot USDT                  : ${usdt:>12,.2f}")
    print(f"  usdt_baseline (state)      : ${baseline:>12,.2f}")
    print(f"  usdt delta                 : ${usdt_delta:>12,.2f}   <- the '$1,838 gap'")
    print(f"  legs_v (shorted-only spot) : ${legs_v:>12,.2f}")
    print(f"  ALL spot coin value        : ${coins_total:>12,.2f}   <- incl. faucet bags")
    print("-" * 72)
    print(f"  EQUITY BY RAIL FORMULA NOW : ${equity_now:>12,.2f}")
    print(f"  vs equity at fire          : ${fired_eq:>12,.2f}")
    print(f"  difference                 : ${equity_now - fired_eq:>12,.2f}")
    print("-" * 72)
    print(f"FUTURES INCOME ATTRIBUTION (last 7d, {rows} records):")
    tot = 0.0
    for k, v in sorted(income.items(), key=lambda x: x[1]):
        print(f"  {k:<24}: ${v:>12,.4f}")
        tot += v
    print(f"  {'TOTAL futures P&L':<24}: ${tot:>12,.4f}   <- real money moved on futures")
    print("-" * 72)
    print("TOP SPOT HOLDINGS (where USDT went, if converted):")
    for a, amt, v in coins[:8]:
        print(f"  {a:<10} {amt:>18,.4f}  ${v:>12,.2f}")
    print("=" * 72)
    print("VERDICT INPUTS:")
    print(f"  * futures realized total   : ${tot:,.2f}")
    print(f"  * usdt delta               : ${usdt_delta:,.2f}")
    print(f"  * unexplained by futures   : ${usdt_delta - tot:,.2f}")
    print(f"  * spot coins held          : ${coins_total:,.2f} (conversion, not loss, if legs)")
    print("=" * 72)


if __name__ == "__main__":
    main()
