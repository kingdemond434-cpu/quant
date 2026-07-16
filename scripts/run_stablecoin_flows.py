"""Daily stablecoin exchange-flow archiver -- starts a NEW orthogonal 40-day forward clock.

Reads the on-chain exchange stablecoin reserve (keyless, libs.data.onchain_flows), appends ONE dated
snapshot per day, and computes netflow = day-over-day reserve change (+ 7d change, + z-score once
enough history). Also records global USDT+USDC totalSupply() as a SECOND orthogonal signal:

  - exchange_reserve: WHERE stablecoins are (on-exchange dry powder / demand for trading)
  - supply:           HOW MANY stablecoins exist (net minting = institutional new capital)

Both signals accumulate on the same 40-day clock. Idempotent (re-running overwrites today's row).
Emits web/stablecoin_flows.json.

    python scripts/run_stablecoin_flows.py
"""

from __future__ import annotations

import json
import statistics
from datetime import UTC, date, datetime
from pathlib import Path

from libs.data.onchain_flows import exchange_reserves, stablecoin_supply

_ARCHIVE = Path("data/stablecoin_flows_archive.json")
_WEB = Path("web/stablecoin_flows.json")
_NEEDS_DAYS = 40


def _load(p: Path, d: object) -> object:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d


def main() -> None:
    res = exchange_reserves()                              # live keyless read
    sup = stablecoin_supply()                              # global supply (orthogonal signal)
    today = date.today().isoformat()
    arch = _load(_ARCHIVE, [])
    if not isinstance(arch, list):
        arch = []
    arch = [a for a in arch if a.get("date") != today]    # idempotent: one snapshot/day
    arch.append({"date": today, "ts": datetime.now(tz=UTC).isoformat(),
                 "total": res["total_reserve_usd"], "per_token": res["per_token"],
                 "per_exchange": res["per_exchange"],
                 "supply_total": sup["total_supply_usd"],
                 "supply_per_token": sup["per_token"]})
    arch = sorted(arch, key=lambda a: a["date"])[-400:]
    _ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVE.write_text(json.dumps(arch, indent=2), "utf-8")

    totals = [float(a["total"]) for a in arch]
    dnet = [totals[i] - totals[i - 1] for i in range(1, len(totals))]
    netflow_1d = round(dnet[-1], 2) if dnet else 0.0
    netflow_7d = round(totals[-1] - totals[-8], 2) if len(totals) >= 8 else None
    z = None
    if len(dnet) >= 10:
        mu, sd = statistics.mean(dnet), statistics.pstdev(dnet)
        z = round((dnet[-1] - mu) / sd, 2) if sd else None

    supplies = [float(a["supply_total"]) for a in arch if a.get("supply_total")]
    supply_1d = round(supplies[-1] - supplies[-2], 2) if len(supplies) >= 2 else None
    supply_7d = round(supplies[-1] - supplies[-8], 2) if len(supplies) >= 8 else None
    forward_days = len(arch)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "sleeve": "stablecoin_exchange_flows",
        "exchange_reserve": {
            "dataset": "on-chain stablecoin exchange reserve",
            "source": "public Ethereum RPC (keyless): USDT+USDC balanceOf on exchange wallets",
            "total_usd": res["total_reserve_usd"], "per_token": res["per_token"],
            "per_exchange": res["per_exchange"], "n_wallets": res["n_wallets"],
            "netflow_1d": netflow_1d, "netflow_7d": netflow_7d, "netflow_z": z,
            "hypothesis": "reserve UP = dry powder on exchanges; sign vs fwd returns = empirical",
        },
        "supply": {
            "dataset": "global USDT+USDC L1 total supply (minting signal)",
            "source": "public Ethereum RPC: USDT+USDC totalSupply()",
            "total_usd": sup["total_supply_usd"], "per_token": sup["per_token"],
            "supply_1d": supply_1d, "supply_7d": supply_7d,
            "hypothesis": ("supply UP = net new minting = institutional demand; orthogonal to "
                           "exchange reserves (WHERE vs HOW MANY)"),
        },
        "forward_days": forward_days, "needs_days": _NEEDS_DAYS,
        "status": (f"ACCUMULATING ({forward_days}/{_NEEDS_DAYS}d) — validate signal->return at day "
                   f"{_NEEDS_DAYS}, not before"),
        # backward-compat flat fields for dashboard / older consumers
        "total_reserve_usd": res["total_reserve_usd"],
        "netflow_1d": netflow_1d, "netflow_z": z,
        "supply_total_usd": sup["total_supply_usd"], "supply_1d": supply_1d,
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    supply_1d_str = f"+{supply_1d:,.0f}" if supply_1d and supply_1d > 0 else (
        f"{supply_1d:,.0f}" if supply_1d is not None else "n/a")
    print(f"stablecoin-flows: reserve ${res['total_reserve_usd']:,.0f} | 1d ${netflow_1d:,.0f}"
          f" | supply ${sup['total_supply_usd']:,.0f} | supply_1d ${supply_1d_str}"
          f" | day {forward_days}/{_NEEDS_DAYS}")


if __name__ == "__main__":
    main()
