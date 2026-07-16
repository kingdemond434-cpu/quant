"""Daily archiver for the Deribit vol surface (ATM IV, 25d-skew, term) -- forward accumulation.

Per-strike implied vol has NO free history, so we snapshot the BTC + ETH surface daily and build our
OWN history -- the input for skew / term-structure / risk-reversal VRP candidates. At ~40 days these
become backtestable through the gauntlet. Rides the always-on executor flywheel. The index DVOL VRP
(already backtested, IC +0.06) is the current evidence; this widens that family forward.

    python scripts/collect_deribit_surface.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.deribit import vol_surface

_LOG = Path("data/deribit_surface.parquet")


def main() -> None:
    ts = datetime.now(tz=UTC)
    rows: list[dict[str, object]] = []
    for cur in ("BTC", "ETH"):
        s = vol_surface(cur)
        if s:
            rows.append({"ts": ts, "currency": cur, **s})
    if not rows:
        raise SystemExit("no vol surface captured (network?)")
    snap = pd.DataFrame(rows)
    if _LOG.exists():
        snap = pd.concat([pd.read_parquet(_LOG), snap], ignore_index=True)
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    snap.to_parquet(_LOG)
    days = snap["ts"].dt.date.nunique()
    print(f"deribit surface @ {ts.date()}: {len(rows)} curs -> {_LOG} ({len(snap)} rows, {days}d)")


if __name__ == "__main__":
    main()
