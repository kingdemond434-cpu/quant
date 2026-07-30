"""DEFI LENDING COLLECTOR -- leverage build-up where forced deleveraging BEGINS.

WHY THIS ONE FIRST, of all the uncollected asymmetric sources. It maps to M_FORCED_DELEVERAGE,
the only mechanism on this desk with a confirmed edge (funding persistence, IC +0.432, t +29.7)
and the best per-mechanism survival rate (2/10). Forced liquidation is the hardest constraint in
crypto: a margin call cannot choose its timing. And DeFi lending is UPSTREAM of perps -- collateral
stress appears in health factors and utilisation before it appears in funding.

MECHANISM, stated so it can be falsified:
    borrowers lever up -> utilisation climbs toward the rate kink -> borrow APY spikes ->
    marginal borrowers are squeezed -> forced unwind -> spot selling -> perp funding moves
The forced participant is the leveraged borrower. The constraint is the liquidation threshold,
which is enforced by code and cannot be negotiated. Persistence: LTV rules are protocol constants,
not sentiment.

FIELDS ARE VERIFIED, NOT ASSUMED. I probed both endpoints before writing this. Two findings that
would have silently poisoned the collector:
  * /pools carries apyBaseBorrow, utilization and ltv as NULL for every lending pool. Building on
    them would have written nulls forever while looking healthy.
  * /lendBorrow reports totalBorrowUsd = $3.27bn for WETH against a /pools tvlUsd of $564m. The
    two endpoints scope differently, so utilisation MUST be computed within one record
    (totalBorrowUsd / totalSupplyUsd), never across them. Cross-endpoint arithmetic here produces
    utilisation > 1, which is impossible and would have been logged as signal.

FREE AND PUBLIC. DefiLlama yields API, no key, no paid tier.

SILENT-FAILURE DEFENCES, because a collector that lies is worse than one that dies:
  * schema contract -- required fields must be present or the run QUARANTINES rather than writes
  * sanity bounds -- utilisation outside [0, 1.05] is dropped per-row and counted
  * coverage floor -- a run yielding fewer than _MIN_ROWS pools writes nothing
  * heartbeat -- separate file so data_vitals can score liveness independently of content
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/defi_lending.jsonl"
HB = ROOT / "data/defi_lending_heartbeat"
QUAR = ROOT / "data/defi_lending_quarantine.json"
CTX = ssl.create_default_context()

POOLS = "https://yields.llama.fi/pools"
BORROW = "https://yields.llama.fi/lendBorrow"
PROJECTS = ("aave-v3", "compound-v3", "morpho-blue", "spark")
CHAINS = ("Ethereum",)
_MIN_ROWS = 20                       # below this the upstream is degraded; write nothing
_REQUIRED = ("pool", "totalBorrowUsd", "totalSupplyUsd", "apyBaseBorrow", "ltv")


def _get(url: str):
    r = urllib.request.Request(url, headers={"User-Agent": "quant-desk/1.0"})
    return json.loads(urllib.request.urlopen(r, timeout=90, context=CTX).read())


def _quarantine(reason: str, detail: dict) -> None:
    QUAR.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), "reason": reason,
                                **detail}, indent=1), "utf-8")
    print(f"  QUARANTINED: {reason}")
    print("  Nothing written. A collector that writes wrong data is worse than one that stops --")
    print("  wrong data is trusted by everything downstream and fails silently.")


def main() -> None:
    ts = datetime.now(tz=UTC)
    print("=== DEFI LENDING COLLECTOR -- where forced deleveraging begins ===")
    print("    mechanism M_FORCED_DELEVERAGE: utilisation -> borrow rate -> squeezed borrower")
    print("    -> forced unwind. Upstream of perp funding.\n")
    try:
        borrow_raw = _get(BORROW)
        pools_raw = _get(POOLS)
    except Exception as e:  # blind-except intentional (BLE001)
        _quarantine("upstream unreachable", {"error": f"{type(e).__name__}: {e}"})
        raise SystemExit(1) from e

    # /lendBorrow returns a bare LIST; /pools returns {"data": [...]}. Verified by probe --
    # assuming a uniform envelope crashed the first run.
    brows = borrow_raw.get("data", borrow_raw) if isinstance(borrow_raw, dict) else borrow_raw
    prows = pools_raw.get("data", pools_raw) if isinstance(pools_raw, dict) else pools_raw
    if not brows or not prows:
        _quarantine("empty upstream payload", {"borrow": len(brows), "pools": len(prows)})
        raise SystemExit(1)

    # SCHEMA CONTRACT -- verified against a live probe, enforced on every run.
    missing = [f for f in _REQUIRED if f not in brows[0]]
    if missing:
        _quarantine("schema drift -- required fields absent", {"missing": missing,
                                                               "saw": sorted(brows[0].keys())})
        raise SystemExit(1)

    meta = {p["pool"]: p for p in prows if p.get("pool")}
    rows, dropped = [], {"impossible_utilisation": 0, "no_supply": 0, "unmatched": 0}
    for b in brows:
        m = meta.get(b.get("pool"))
        if not m:
            dropped["unmatched"] += 1
            continue
        if m.get("project") not in PROJECTS or m.get("chain") not in CHAINS:
            continue
        sup = b.get("totalSupplyUsd")
        bor = b.get("totalBorrowUsd")
        if not sup or sup <= 0:
            dropped["no_supply"] += 1
            continue
        # WITHIN ONE RECORD ONLY. Cross-endpoint arithmetic gives utilisation > 1 (verified:
        # WETH borrow $3.27bn vs pools tvl $564m -- different scoping, same asset).
        util = float(bor or 0.0) / float(sup)
        if not (0.0 <= util <= 1.05):
            dropped["impossible_utilisation"] += 1
            continue
        rows.append({"ts": ts.isoformat(), "pool": b["pool"], "project": m.get("project"),
                     "chain": m.get("chain"), "symbol": m.get("symbol"),
                     "supply_usd": round(float(sup), 2), "borrow_usd": round(float(bor or 0), 2),
                     "utilisation": round(util, 5),
                     "borrow_apy": b.get("apyBaseBorrow"), "supply_apy": m.get("apyBase"),
                     "ltv": b.get("ltv"), "debt_ceiling_usd": b.get("debtCeilingUsd"),
                     "tvl_usd": m.get("tvlUsd")})

    if len(rows) < _MIN_ROWS:
        _quarantine("coverage below floor", {"rows": len(rows), "floor": _MIN_ROWS,
                                             "dropped": dropped})
        raise SystemExit(1)

    with OUT.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    HB.write_text(f"{ts.isoformat()} rows={len(rows)}", "utf-8")
    if QUAR.exists():
        QUAR.unlink()                                  # clear a stale quarantine on a good run

    tot_sup = sum(r["supply_usd"] for r in rows)
    tot_bor = sum(r["borrow_usd"] for r in rows)
    hot = sorted([r for r in rows if r["supply_usd"] > 5e7], key=lambda r: -r["utilisation"])[:6]
    print(f"  {len(rows)} pools across {len({r['project'] for r in rows})} protocols")
    print(f"  aggregate supply ${tot_sup/1e9:.2f}bn  borrow ${tot_bor/1e9:.2f}bn  "
          f"system utilisation {tot_bor/max(tot_sup,1):.1%}")
    print(f"  dropped: {dropped}\n")
    print(f"  {'project':<13}{'symbol':<10}{'util':>8}{'borrowAPY':>11}{'supply$M':>11}")
    for r in hot:
        print(f"  {r['project']:<13}{str(r['symbol'])[:9]:<10}{r['utilisation']:>7.1%}"
              f"{(r['borrow_apy'] or 0):>10.2f}%{r['supply_usd']/1e6:>11.0f}")
    print("\n  HIGH UTILISATION IS THE SIGNAL, NOT THE ALPHA. It marks where borrowers sit closest")
    print("  to the rate kink -- the population that is squeezed first when rates move. Whether")
    print("  that predicts anything tradeable is a Stage-A question this collector merely feeds.")
    print(f"\n  -> {OUT}  (heartbeat {HB.name})")


if __name__ == "__main__":
    main()
