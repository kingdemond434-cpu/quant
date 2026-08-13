#!/usr/bin/env python3
"""Binance Vision archive fetcher -- the desk's only working route to Binance USD-M perp history.

WHY THIS EXISTS. api.binance.com and fapi.binance.com answer HTTP 451 from this box (geo-block,
recorded in the venue notes), which for weeks read as "Binance is unreachable". data.binance.vision
is a DIFFERENT host -- the public archive CDN -- and it serves full-depth monthly kline and
funding zips with no key and no geo-block (probed 2026-08-04: HTTP 200, full content-length).
The lesson is L0052's shape again: a blocked endpoint is a property of the ENDPOINT, never of the
venue. This module is deliberately dumb: download, unzip, parse, cache as .npz -- provenance in
the filename, no resampling, no cleverness.

    python scripts/fetch_binance_vision.py --symbols BTCUSDT,ETHUSDT,SOLUSDT \
        --interval 5m --start 2023-08 --end 2026-07
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
_CACHE = _ROOT / "data" / "binance_vision"
_BASE = "https://data.binance.vision/data/futures/um/monthly"

#: kline CSV columns (Binance futures spec): open_time, open, high, low, close, volume,
#: close_time, quote_volume, count, taker_buy_volume, taker_buy_quote_volume, ignore
_KCOLS = ("open_time", "open", "high", "low", "close", "volume", "quote_volume")


def _months(start: str, end: str) -> list[str]:
    y0, m0 = (int(x) for x in start.split("-"))
    y1, m1 = (int(x) for x in end.split("-"))
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _get(url: str) -> bytes | None:
    """Bytes, or None for a month the archive says is GENUINELY ABSENT (HTTP 404). Anything else
    raises.

    R0466. This was `except Exception: return None`, and the comment on it -- "absent month
    (listing gaps)" -- was the defect written down: a 403, a 429, a 5xx and a read timeout all
    became "absent month" and were appended to `missing`. The caller then built a price history
    with holes in it and reported those holes as the archive's, so a venue refusing or throttling
    this box produced a SHORT SERIES rather than a loud failure, and every downstream statistic
    was computed over a silently truncated sample. Only a 404 is evidence about the archive; the
    rest is evidence about the connection (WS-005/L1.28a).
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None                 # the archive answered: this month is not published
        raise RuntimeError(
            f"binance-vision refused {url}: HTTP {exc.code} {exc.reason}. This is NOT an absent "
            f"month -- treating it as one would silently shorten the series.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"binance-vision unreachable for {url}: {type(exc).__name__}: {exc}. Whether this "
            f"month exists is UNMEASURED, not absent.") from exc


def fetch_klines(symbol: str, interval: str, months: list[str]) -> dict[str, np.ndarray]:
    cols: dict[str, list[float]] = {k: [] for k in _KCOLS}
    missing: list[str] = []
    for mo in months:
        raw = _get(f"{_BASE}/klines/{symbol}/{interval}/{symbol}-{interval}-{mo}.zip")
        if raw is None:
            missing.append(mo)
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name = z.namelist()[0]
            text = z.read(name).decode("utf-8")
        for row in csv.reader(io.StringIO(text)):
            if not row or not row[0].isdigit():   # some months carry a header row, some do not
                continue
            cols["open_time"].append(float(row[0]))
            cols["open"].append(float(row[1]))
            cols["high"].append(float(row[2]))
            cols["low"].append(float(row[3]))
            cols["close"].append(float(row[4]))
            cols["volume"].append(float(row[5]))
            cols["quote_volume"].append(float(row[7]))
    out = {k: np.asarray(v, dtype="float64") for k, v in cols.items()}
    order = np.argsort(out["open_time"], kind="stable")
    out = {k: v[order] for k, v in out.items()}
    # timestamps: Binance flipped open_time to MICROseconds in the 2025+ archives (13 -> 16
    # digits). Normalise everything to milliseconds so downstream never sees the seam.
    ot = out["open_time"]
    ot = np.where(ot > 1e14, ot / 1000.0, ot)
    out["open_time"] = ot
    keep = np.concatenate([[True], np.diff(ot) > 0])
    out = {k: v[keep] for k, v in out.items()}
    out["_missing_months"] = np.asarray(missing, dtype=object)
    return out


def fetch_funding(symbol: str, months: list[str]) -> dict[str, np.ndarray]:
    ts: list[float] = []
    rate: list[float] = []
    for mo in months:
        raw = _get(f"{_BASE}/fundingRate/{symbol}/{symbol}-fundingRate-{mo}.zip")
        if raw is None:
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            text = z.read(z.namelist()[0]).decode("utf-8")
        for row in csv.reader(io.StringIO(text)):
            if not row or not row[0].isdigit():
                continue
            ts.append(float(row[0]))
            rate.append(float(row[2]))
    t = np.asarray(ts, dtype="float64")
    t = np.where(t > 1e14, t / 1000.0, t)
    r = np.asarray(rate, dtype="float64")
    order = np.argsort(t, kind="stable")
    return {"time": t[order], "rate": r[order]}


def load_or_fetch(symbol: str, interval: str, start: str, end: str) -> dict[str, np.ndarray]:
    """Cache-through loader. The cache file IS the provenance record."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    f = _CACHE / f"{symbol}-{interval}-{start}-{end}.npz"
    if f.exists():
        with np.load(f, allow_pickle=True) as z:
            return {k: z[k] for k in z.files}
    months = _months(start, end)
    data = fetch_klines(symbol, interval, months)
    fund = fetch_funding(symbol, months)
    data["funding_time"], data["funding_rate"] = fund["time"], fund["rate"]
    np.savez_compressed(f, **data)
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--start", default="2023-08")
    ap.add_argument("--end", default="2026-07")
    args = ap.parse_args()
    report = {}
    for sym in args.symbols.split(","):
        d = load_or_fetch(sym.strip(), args.interval, args.start, args.end)
        n = len(d["open_time"])
        t0 = datetime.fromtimestamp(d["open_time"][0] / 1000, tz=UTC)
        t1 = datetime.fromtimestamp(d["open_time"][-1] / 1000, tz=UTC)
        report[sym] = {"bars": n, "first": t0.isoformat()[:16], "last": t1.isoformat()[:16],
                       "funding_rows": len(d.get("funding_time", [])),
                       "missing_months": list(d.get("_missing_months", []))}
        print(f"{sym}: {n} bars {t0:%Y-%m-%d}..{t1:%Y-%m-%d}, "
              f"{report[sym]['funding_rows']} funding rows, "
              f"missing={report[sym]['missing_months'] or 'none'}")
    (_CACHE / "fetch_report.json").write_text(json.dumps(report, indent=2), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
