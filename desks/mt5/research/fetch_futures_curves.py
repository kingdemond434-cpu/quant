"""Accrue genuine contract-level gold and WTI curves for MT5 research.

Continuous front-month prices cannot identify roll yield or calendar spreads. This collector keeps
each delayed public contract separately, including its expiry and volume, and publishes a long
point-in-time panel. Missing contracts remain missing; no synthetic curve is manufactured.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "futures_curves"
REPORT = BASE / "reports" / "futures_curve_coverage.json"
UA = "Mozilla/5.0 (compatible; quant-research/1.0)"
MONTH_CODE = dict(zip(range(1, 13), "FGHJKMNQUVXZ", strict=True))
PRODUCTS = {
    "GC": {"suffix": "CMX", "months": (2, 4, 6, 8, 10, 12)},
    "CL": {"suffix": "NYM", "months": tuple(range(1, 13))},
}


def contract_symbol(root: str, year: int, month: int) -> str:
    return f"{root}{MONTH_CODE[month]}{year % 100:02d}.{PRODUCTS[root]['suffix']}"


def fetch_contract(symbol: str) -> tuple[pd.DataFrame, dict]:
    encoded = urllib.parse.quote(symbol, safe="")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
           "?period1=0&period2=4102444800&interval=1d&events=history")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 404):
            return pd.DataFrame(), {"symbol": symbol, "status": "NOT_LISTED"}
        raise
    result = (payload.get("chart", {}).get("result") or [])
    if not result:
        return pd.DataFrame(), {"symbol": symbol, "status": "NO_RESULT"}
    raw = result[0]
    stamps = raw.get("timestamp") or []
    quote = (raw.get("indicators", {}).get("quote") or [{}])[0]
    meta = raw.get("meta") or {}
    if not stamps:
        return pd.DataFrame(), {"symbol": symbol, "status": "EMPTY"}
    frame = pd.DataFrame({
        "date": pd.to_datetime(stamps, unit="s", utc=True).normalize(),
        "open": quote.get("open"), "high": quote.get("high"),
        "low": quote.get("low"), "close": quote.get("close"),
        "volume": quote.get("volume"),
    }).dropna(subset=["close"])
    expiry = meta.get("expireDate")
    frame["symbol"] = symbol
    frame["expiration"] = (pd.to_datetime(expiry, unit="s", utc=True).normalize()
                            if expiry else pd.NaT)
    frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    return frame, {"symbol": symbol, "status": "OK", "rows": len(frame),
                   "expiration": None if not expiry else str(frame["expiration"].iloc[0])}


def build_curve(contracts: list[pd.DataFrame], root: str) -> pd.DataFrame:
    frame = pd.concat(contracts, ignore_index=True)
    # Yahoo mixes timezone-aware chart stamps, timezone-naive metadata and missing expiries across
    # contract vintages. Normalize both columns before subtraction; an unknown expiry cannot define
    # a curve rank and is retained in coverage but excluded from the measured curve.
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.normalize()
    frame["expiration"] = pd.to_datetime(
        frame["expiration"], utc=True, errors="coerce",
    ).dt.normalize()
    frame = frame.dropna(subset=["date", "expiration", "close"])
    frame = frame.sort_values(["date", "expiration", "symbol"])
    frame["root"] = root
    frame["days_to_expiry"] = (frame["expiration"] - frame["date"]).dt.days
    frame = frame[frame["days_to_expiry"] > 0].copy()
    frame["curve_rank"] = frame.groupby("date").cumcount() + 1
    front = frame[frame["curve_rank"] == 1][["date", "close", "expiration"]].rename(
        columns={"close": "front_close", "expiration": "front_expiration"})
    nxt = frame[frame["curve_rank"] == 2][["date", "close", "expiration"]].rename(
        columns={"close": "next_close", "expiration": "next_expiration"})
    pair = front.merge(nxt, on="date", how="left")
    tenor = (pair["next_expiration"] - pair["front_expiration"]).dt.days
    pair["calendar_spread"] = pair["next_close"] - pair["front_close"]
    pair["annualized_roll_yield"] = -(pair["next_close"] / pair["front_close"] - 1.0) * 365 / tenor
    return frame.merge(pair[["date", "calendar_spread", "annualized_roll_yield"]], on="date")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years-back", type=int, default=4)
    parser.add_argument("--years-forward", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args(argv)
    year = datetime.now(UTC).year
    coverage, usable = [], 0
    for root, spec in PRODUCTS.items():
        frames = []
        for y in range(year - args.years_back, year + args.years_forward + 1):
            for month in spec["months"]:
                symbol = contract_symbol(root, y, month)
                try:
                    frame, row = fetch_contract(symbol)
                except Exception as exc:
                    frame, row = pd.DataFrame(), {"symbol": symbol, "status": "FAILED",
                                                  "error": f"{type(exc).__name__}: {exc}"}
                coverage.append(row)
                if not frame.empty:
                    frames.append(frame)
                time.sleep(max(args.sleep, 0.0))
        if frames:
            panel = build_curve(frames, root)
            OUT.mkdir(parents=True, exist_ok=True)
            panel.to_parquet(OUT / f"{root}_curve.parquet", index=False, compression="zstd")
            usable += int(panel["annualized_roll_yield"].notna().sum())
    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Yahoo delayed contract quotes; research only",
        "contracts": coverage,
        "usable_curve_dates": usable,
        "promotion_authority": False,
        "status": "MEASURED" if usable else "UNMEASURED",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "usable_curve_dates": usable,
                      "contracts_attempted": len(coverage)}, indent=2))
    return 0 if usable else 2


if __name__ == "__main__":
    raise SystemExit(main())
