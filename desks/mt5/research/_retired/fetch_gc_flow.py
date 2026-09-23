"""COMEX GC futures bars with REAL traded volume, for the MT5 gold desk.

WHY THIS EXISTS, AND WHAT IT HONESTLY IS NOT

MT5 spot XAUUSD is OTC. There is no consolidated book, `real_volume` is zero on
every one of the desk's 49,735 gold bars (checked, not assumed), and
`tick_volume` counts QUOTE UPDATES rather than contracts traded. So the desk has
never had a volume series for gold -- only a proxy for how often its own broker
requoted.

GC is the centralised venue where gold price discovery actually happens, and a
free bar feed carries its true contract volume. That is a genuinely new input
rather than another transform of closes we already own, which is the only kind
of input that raises the book's effective breadth (measured: 5.64 independent
axes across 22 symbols, so more signals on the same series buy nothing).

WHAT THIS CANNOT GET, AND WILL NOT PRETEND TO

No aggressor side. No book depth. No cancellations. Cumulative delta, order-book
imbalance and absorption all need MBO/MBP data that no free source carries, and
a "delta" reconstructed from bar direction is a guess wearing a quantitative
name. If the ladder needs those, it needs a paid feed (Databento GLBX.MDP3 or
CME DataMine) and that is a purchase decision, not a fetch.

WHY THE INTERVALS STOP AT 15 MINUTES

The cost gate already ruled the fast end out. Gold's honest round trip is 0.39
$/oz against a 1-minute sigma of 0.88, so a 1-minute signal needs an information
coefficient of 0.557 -- larger than anything published anywhere. 15 minutes needs
0.144, 30 minutes 0.102, an hour 0.072. Order-flow imbalance's native edge lives
at seconds and decays fast; ours has to survive to 15 minutes or it does not pay.
Fetching 1-minute bars would be collecting data for a horizon the desk cannot
trade, so the default intervals are the ones that can.

RUN THIS ON THE VPS. The research container's egress proxy denies Yahoo by
policy (403 on CONNECT), so it cannot be tested from there -- which is itself
the reason the fetch belongs on the box that has the network.

    python fetch_gc_flow.py --dry          # show the plan, touch nothing
    python fetch_gc_flow.py                # 1h + 15m, incremental
    python fetch_gc_flow.py --interval 1h --range 2y
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
OUT_DIR = _DESK / "data" / "gcflow"
REPORT = _DESK / "reports" / "gc_flow_coverage.json"
SYMBOL = "GC=F"

# Yahoo's own retention per interval. Asking for more silently returns less,
# which would look like a gap in the market rather than a limit of the source.
MAX_RANGE = {"15m": "60d", "30m": "60d", "1h": "730d", "1d": "10y"}
DEFAULT_INTERVALS = ("1h", "15m")
UA = "Mozilla/5.0 (X11; Linux x86_64) research-bar-fetch/1.0"


def fetch(interval: str, rng: str, retries: int = 4) -> pd.DataFrame:
    """One interval from Yahoo's chart endpoint, with backoff.

    Network failures retry; a POLICY denial (403/407 from a proxy) does not.
    Retrying a refusal just burns time and hides the real cause in a stack of
    identical errors.
    """
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}"
           f"?range={rng}&interval={interval}")
    delay = 2.0
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.load(r)
            break
        except urllib.error.HTTPError as e:                     # noqa: PERF203
            if e.code in (401, 403, 407):
                raise SystemExit(
                    f"{SYMBOL} {interval}: HTTP {e.code} -- this is an access or "
                    f"proxy POLICY denial, not a transient failure. Run this on "
                    f"the VPS; retrying here will not change the answer.") from e
            last = e
        except Exception as e:                                  # noqa: BLE001
            # A proxy that refuses CONNECT reports through URLError, not
            # HTTPError, so the status-code check above never sees it. Without
            # this the run burns its whole backoff ladder on a refusal that
            # cannot change, and the operator reads "giving up after 4 tries"
            # as a flaky network instead of a policy denial.
            msg = str(e)
            if "Tunnel connection failed" in msg and (
                    "403" in msg or "407" in msg):
                raise SystemExit(
                    f"{SYMBOL} {interval}: the egress proxy refused CONNECT "
                    f"({msg.strip()}). This is a POLICY denial, not a transient "
                    f"failure -- run this on the VPS, which has the network.") from e
            last = e
        if attempt < retries - 1:
            time.sleep(delay)
            delay *= 2
    else:
        raise SystemExit(f"{SYMBOL} {interval}: giving up after {retries} tries: {last}")

    res = payload.get("chart", {}).get("result")
    if not res:
        err = payload.get("chart", {}).get("error")
        raise SystemExit(f"{SYMBOL} {interval}: no result ({err})")
    r0 = res[0]
    ts = r0.get("timestamp") or []
    q = (r0.get("indicators", {}).get("quote") or [{}])[0]
    if not ts:
        raise SystemExit(f"{SYMBOL} {interval}: empty series")
    df = pd.DataFrame({
        "open": q.get("open"), "high": q.get("high"),
        "low": q.get("low"), "close": q.get("close"),
        "volume": q.get("volume"),
    }, index=pd.to_datetime(pd.Series(ts, dtype="int64"), unit="s", utc=True))
    df.index.name = "time"
    # A bar with no close is not a flat bar, it is an absent bar. Dropping it
    # keeps a hole visible as a hole; filling it would manufacture a print.
    df = df.dropna(subset=["close"]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def merge_write(df: pd.DataFrame, path: Path) -> tuple[int, int]:
    """Append to whatever is on disk, newest wins on collision. Idempotent."""
    before = 0
    if path.exists():
        old = pd.read_parquet(path)
        before = len(old)
        df = pd.concat([old, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd")
    return before, len(df)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", action="append", choices=sorted(MAX_RANGE),
                    help="repeatable; default 1h and 15m")
    ap.add_argument("--range", dest="rng", default=None,
                    help="override; capped at the source's retention")
    ap.add_argument("--dry", action="store_true",
                    help="print the plan and exit without fetching or writing")
    args = ap.parse_args()
    intervals = tuple(args.interval) if args.interval else DEFAULT_INTERVALS

    print(f"GC FLOW FETCH  {SYMBOL} -> {OUT_DIR}")
    rows = []
    for iv in intervals:
        rng = args.rng or MAX_RANGE[iv]
        if args.rng and args.rng != MAX_RANGE[iv]:
            print(f"  note: {iv} retention is {MAX_RANGE[iv]}; asking for "
                  f"{args.rng} returns at most that and the shortfall is the "
                  f"source's, not the market's")
        path = OUT_DIR / f"GC_{iv}.parquet"
        if args.dry:
            have = len(pd.read_parquet(path)) if path.exists() else 0
            print(f"  would fetch {iv} range={rng} -> {path.name} "
                  f"(currently {have} bars)")
            continue
        df = fetch(iv, rng)
        before, after = merge_write(df, path)
        vol = int(df["volume"].fillna(0).gt(0).sum())
        rows.append({
            "interval": iv, "range": rng, "fetched": len(df),
            "bars_before": before, "bars_after": after,
            "new_bars": after - before,
            "bars_with_volume": vol,
            "first": str(df.index.min()), "last": str(df.index.max()),
            "path": str(path),
        })
        print(f"  {iv:>4}: fetched {len(df):>6}  new {after - before:>6}  "
              f"total {after:>6}  volume on {vol}/{len(df)} bars  "
              f"[{df.index.min()} .. {df.index.max()}]")
        if vol == 0:
            print("        WARNING: every volume is zero or null. That is the "
                  "one field this fetch exists for -- treat the series as "
                  "UNUSABLE rather than as a market with no trading.")
    if args.dry:
        print("\n(dry run -- nothing fetched, nothing written)")
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(
        {"symbol": SYMBOL, "fetched_at": pd.Timestamp.utcnow().isoformat(),
         "intervals": rows,
         "known_limits": {
             "aggressor_side": "UNAVAILABLE from this source -- needs MBO/MBP",
             "book_depth": "UNAVAILABLE from this source",
             "note": "bar volume is real contract volume, unlike MT5 tick_volume",
         }}, indent=1), "utf-8")
    print(f"\nwritten: {REPORT}")
    print("Next: join GC volume onto XAUUSD H1 and test whether it beats "
          "tick_volume\n      at 15m/1h. If real volume adds nothing there, "
          "paid book data will not\n      either, and that is the cheapest "
          "possible way to learn it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
