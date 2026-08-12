"""Daily archiver for Binance derivative metrics that are 30-day-capped (no deep history).

Open interest, global long/short account ratio, and taker buy/sell ratio cannot be backtested (the
API only serves ~30 days), so we snapshot them daily and accumulate our OWN history -- a future
alpha factory. Each run appends today's reading per liquid perp to data/crypto_metrics.parquet.
Schedule daily; every run adds information advantage.

MEASURED 2026-08-12: this organ had never been scheduled -- 0 cron/systemd lines. It is the sole
feed for data/crypto_metrics.parquet, which run_derivative_shadow.py's two pre-registered forward
clocks (oi_divergence, ls_contrarian) read to count `days_accumulated` toward their 40-day bar.
With no archiver running, that count could not advance regardless of elapsed calendar time.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    # WITHOUT THIS the script dies on `ModuleNotFoundError: No module named 'libs'` when invoked
    # as `python scripts/collect_binance_metrics.py`, which is exactly how a manifest line would
    # call it -- the other reason, alongside never being scheduled, that this archiver has never
    # actually run as intended.
    sys.path.insert(0, str(_ROOT))

from libs.data.crypto_source import (  # noqa: E402
    fetch_long_short_ratio,
    fetch_open_interest,
    fetch_taker_ratio,
    list_liquid_perps,
)
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_LOG = Path("data/crypto_metrics.parquet")


def main() -> None:
    _law_guard()
    ts = datetime.now(tz=UTC)
    try:
        universe = list_liquid_perps(top_n=100)
    except Exception as exc:
        # UNCAUGHT BEFORE THIS: the per-symbol try/except below only ever covered the METRIC
        # fetches, never the universe-discovery call itself, so a failure here produced a bare
        # traceback in the cron log instead of the same clean refusal every other failure mode on
        # this organ already has. Fail-visible, matching the rest of the desk's vocabulary, rather
        # than a stack trace nobody scheduled to read.
        raise SystemExit(f"REFUSED: could not list the tradeable universe "
                         f"({type(exc).__name__}: {exc}) -- no metrics captured") from exc
    rows: list[dict[str, object]] = []
    for sym in universe:
        try:
            oi = fetch_open_interest(sym)
            ls = fetch_long_short_ratio(sym)
            tk = fetch_taker_ratio(sym)
        except Exception:  # transient; skip this symbol today
            continue
        rows.append({
            "ts": ts, "symbol": sym, "open_interest": oi,
            "ls_ratio": float(ls["ls_ratio"].iloc[-1]) if not ls.empty else float("nan"),
            "taker_ratio": float(tk["taker_ratio"].iloc[-1]) if not tk.empty else float("nan"),
        })
    if not rows:
        raise SystemExit("no metrics captured (network?)")
    snap = pd.DataFrame(rows)
    if _LOG.exists():
        snap = pd.concat([pd.read_parquet(_LOG), snap], ignore_index=True)
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    snap.to_parquet(_LOG)
    days = snap["ts"].dt.date.nunique()
    print(f"archived {len(rows)} symbols @ {ts.date()} -> {_LOG} "
          f"({len(snap)} rows, {days} distinct days)")


if __name__ == "__main__":
    main()
