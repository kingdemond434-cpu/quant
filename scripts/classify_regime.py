"""Classify the current crypto market regime (trend x vol) from BTC daily bars.

Writes data/crypto_regime.json so the executor and dashboard can show the LIVE regime and let every
sleeve's regime fit (from crypto_portfolio.json's regime table) be read in context. Cheap -- one
daily BTC kline pull. Run once per UTC day (the always-on executor calls it; run_crypto_testnet).

    python scripts/classify_regime.py
"""

from __future__ import annotations

import argparse
import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from libs.data.crypto_source import fetch_klines

if TYPE_CHECKING:
    import pandas as pd

_OUT = Path("data/crypto_regime.json")
#: R0006: _OUT is OVERWRITTEN every run, so yesterday's regime fingerprint was destroyed daily and
#: the desk could never ask "what regime was it when this trade was opened / this screen ran".
#: That history is unrecoverable once lost -- Binance serves the bars again, but not the desk's own
#: dated reading of them -- so the same payload is also APPENDED here, one line per UTC day.
#: Append-only and idempotent per day: re-running within a day replaces that day's line rather
#: than stacking duplicates, so the executor's repeated calls cannot inflate the record.
_HIST = Path("data/crypto_regime_history.jsonl")


def _append_history(row: dict[str, object], path: Path = _HIST) -> None:
    """Append today's regime row, replacing any existing row for the same UTC date."""
    day = str(row["updated"])[:10]
    kept: list[str] = []
    try:
        for ln in path.read_text("utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                if str(json.loads(ln).get("updated", ""))[:10] == day:
                    continue          # same UTC day -> this run supersedes it
            except json.JSONDecodeError:
                pass                  # never drop a line we cannot parse; history is evidence
            kept.append(ln)
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join([*kept, json.dumps(row)]) + "\n", "utf-8")
    tmp.replace(path)                 # same-dir tmp + replace: never a torn history file


def classify(close: np.ndarray, updated: str) -> dict[str, object]:
    """Classify the regime from a close series ENDING at the day being classified.

    Pulled out of main() so the backfill runs the identical computation rather than a lookalike
    reimplementation -- two copies of a classifier drift, and a history labelled by a drifted
    copy is worse than no history because nothing announces the seam. Every window here reads
    backwards from the end of ``close``, so passing a truncated prefix yields exactly what this
    script would have written on that day: the backfill is causal by construction, not by care.
    """
    rets = np.diff(close) / close[:-1]
    base = close[-61] if len(close) > 61 else close[0]
    mom = float(close[-1] / base - 1.0)
    trend = "bull" if mom >= 0 else "bear"
    rv14 = float(np.std(rets[-14:])) if len(rets) >= 14 else float(np.std(rets))
    # median of trailing 14d realized vol over the last ~year -> the high/low-vol divider
    window = [float(np.std(rets[i - 14:i])) for i in range(14, len(rets))][-365:]
    rv_med = float(np.median(window)) if window else rv14
    vol = "high_vol" if rv14 > rv_med else "low_vol"
    return {
        "updated": updated,
        "regime": f"trend:{trend} / vol:{vol}",
        "trend": trend,
        "vol": vol,
        "btc_60d_mom": round(mom, 4),
        "rv14_ann": round(rv14 * (365 ** 0.5), 3),
    }


def backfill(df: pd.DataFrame, *, days: int = 365, path: Path | None = None) -> int:
    """Reconstruct the last ``days`` of regime rows from the bar history, causally.

    Without this the history is empty on the day it is introduced and stays useless for months,
    which is the whole reason the daily fingerprint was worth preserving. Each row is classified
    on the prefix ending at that bar, so a backfilled row equals what the live run would have
    written. Existing rows win: _append_history supersedes per UTC day, so a backfill can never
    overwrite a genuinely-live reading with a reconstruction.
    """
    # Resolved at CALL time, and threaded explicitly into _append_history: that function's
    # `path=_HIST` default is bound when the module is imported, so relying on it here would
    # write to the real data/ directory even when a caller has redirected the history.
    out = path if path is not None else _HIST
    close_all = df["close"].astype(float).to_numpy()
    stamps = df["timestamp"].tolist()
    n = len(close_all)
    written = 0
    existing: set[str] = set()
    try:
        for ln in out.read_text("utf-8").splitlines():
            if ln.strip():
                with contextlib.suppress(json.JSONDecodeError):
                    existing.add(str(json.loads(ln).get("updated", ""))[:10])
    except FileNotFoundError:
        pass
    for i in range(max(62, n - days), n):
        day = str(stamps[i])[:10]
        if day in existing:
            continue                  # never overwrite a live reading with a reconstruction
        _append_history(classify(close_all[:i + 1], str(stamps[i])), path=out)
        existing.add(day)             # a re-stamp within one run must not re-enter the file
        written += 1
    return written


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backfill", type=int, metavar="DAYS", default=0,
                    help="also reconstruct this many days of history from the bars (causal)")
    args = ap.parse_args(argv)

    df = fetch_klines("BTCUSDT", interval="1d")
    if df.empty or "close" not in df:
        raise SystemExit("no BTC klines")
    close = df["close"].astype(float).to_numpy()
    out = classify(close, datetime.now(tz=UTC).isoformat())
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    _append_history(out)
    msg = (f"regime: {out['regime']}  (BTC 60d mom {out['btc_60d_mom']:+.1%}, "
           f"rv14 {out['rv14_ann']:.0%} ann)")
    if args.backfill > 0:
        msg += f"  [backfilled {backfill(df, days=args.backfill)} historical days]"
    print(msg)


if __name__ == "__main__":
    main()
