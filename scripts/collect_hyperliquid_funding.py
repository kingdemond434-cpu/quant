"""Archive Hyperliquid per-asset funding + the Binance<->HL cross-venue spread (forward only).

Hyperliquid exposes only CURRENT funding (no history via API), so the cross-venue carry sleeve can
only be built by accumulating snapshots from today. Each run appends one row per asset: HL funding,
Binance funding, and the spread (venue-specific leverage-demand divergence -- a candidate orthogonal
carry signal). Starts a forward clock; the sleeve is BACKTESTABLE only after ~250 daily obs accrue.
No alpha claim yet -- the honest forward-archive for the next decorrelated breadth candidate.

    python scripts/collect_hyperliquid_funding.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import current_funding
from libs.data.freesources import hyperliquid_funding

_ARCH = Path("data/hyperliquid_funding.parquet")
_WEB = Path("web/hyperliquid.json")
_CLOCK = Path("data/hyperliquid_since")


def main() -> None:
    hl = hyperliquid_funding()                       # {COIN: funding}
    bn = current_funding()                           # {SYMBOLUSDT: funding}
    if not hl:
        raise SystemExit("hyperliquid funding empty")
    now = datetime.now(tz=UTC)
    rows = []
    for coin, hlf in hl.items():
        bnf = bn.get(f"{coin}USDT")
        rows.append({"timestamp": now, "coin": coin, "hl_funding": hlf,
                     "bn_funding": bnf, "spread": (hlf - bnf) if bnf is not None else None})
    df = pd.DataFrame(rows)
    if _ARCH.exists():
        df = pd.concat([pd.read_parquet(_ARCH), df], ignore_index=True)
    _ARCH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_ARCH, index=False)
    if not _CLOCK.exists():
        _CLOCK.write_text(now.isoformat(), "utf-8")
    start = datetime.fromisoformat(_CLOCK.read_text("utf-8"))
    days = (now - start).days
    snaps = int(df["timestamp"].nunique())

    both = df[df["spread"].notna()]
    matched = sorted(both["coin"].unique().tolist())
    spreads = both[both["timestamp"] == both["timestamp"].max()]["spread"].to_numpy()
    out = {
        "updated": now.isoformat(),
        "hl_assets": len(hl), "binance_matched": len(matched),
        "forward_days": days, "snapshots": snaps, "ready_at_obs": 250,
        "spread_mean": round(float(np.mean(spreads)), 7) if len(spreads) else None,
        "spread_dispersion": round(float(np.std(spreads)), 7) if len(spreads) else None,
        "status": "ACCRUING (forward-only; HL has no funding history)",
        "note": ("Cross-venue funding spread (Binance vs Hyperliquid) = next decorrelated carry "
                 "candidate. No HL history exists, so it archives forward and becomes backtestable "
                 f"after ~250 daily obs (now {snaps}). NOT an alpha yet -- breadth in the making."),
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"hyperliquid funding: {len(hl)} HL assets, {len(matched)} matched to Binance | "
          f"spread disp {out['spread_dispersion']} | forward day {days}, {snaps} snapshots")


if __name__ == "__main__":
    main()
