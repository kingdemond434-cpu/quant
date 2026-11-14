"""Gold and WTI contract curves for MT5 research: REFUSED ON TERMS, this collector opens no socket.

Continuous front-month prices cannot identify roll yield or calendar spreads, so this collector
used to keep each delayed contract separately (expiry, volume) in a long point-in-time panel. Its
only source was Yahoo's chart endpoint, and Yahoo's terms refuse automated fetches on every route
(Audit HOLD on #898, 2026-11-14; the same standard #1177 applied to FRED). So the fetch is REMOVED,
not switched off, and no later session can re-enable it by flipping a flag. `main` writes a
BLOCKED_ON_TERMS record with its missed-growth line and leaves the held parquets in
data/futures_curves/ exactly as they are, labelled by their `source_id`/`source_class` columns and
listed in the report. The curve shape helpers stay: they are pure, and a lawful source (the
exchange's own settlements, once its terms read OPEN) would feed them.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "futures_curves"
REPORT = BASE / "reports" / "futures_curve_coverage.json"
#: The registry row this collector's output belongs to. Its class travels with the report, and
#: `curve_strategy_screen.mint_permission` reads it before any cell is minted.
SOURCE_ID = "yahoo_futures"
REGISTRY = BASE / "research" / "futures_state_sources.json"
YAHOO_TERMS = ("BLOCKED_ON_TERMS: Yahoo (query1.finance.yahoo.com) refuses automated fetches on "
               "every route (Audit HOLD on #898, 2026-11-14); no socket is opened")
MISSED_GROWTH = {
    "mechanism": "yahoo_futures_terms_refusal",
    "lost": "the daily refresh of the GC and CL contract curves (roll yield, calendar spreads, "
            "contract volume) that curve_strategy_screen reads for its idea rows",
    "stand_in": "the held data/futures_curves/*_curve.parquet panels (labelled, not refreshed); "
                "exchange settlements only once cme_settlements reads OPEN",
    "verdict": "a gap, not a zero",
}


def source_class(registry: Path = REGISTRY) -> str:
    """The registry's terms class for SOURCE_ID; UNREADABLE when the row cannot be read."""
    try:
        doc = json.loads(registry.read_text(encoding="utf-8"))
        for row in doc.get("sources") or []:
            if isinstance(row, dict) and row.get("id") == SOURCE_ID:
                return str(row.get("terms") or "MISSING")
    except (OSError, ValueError, AttributeError):
        return "UNREADABLE"
    return "MISSING"


MONTH_CODE = dict(zip(range(1, 13), "FGHJKMNQUVXZ", strict=True))
PRODUCTS = {
    "GC": {"suffix": "CMX", "months": (2, 4, 6, 8, 10, 12)},
    "CL": {"suffix": "NYM", "months": tuple(range(1, 13))},
}
CODE_MONTH = {code: month for month, code in MONTH_CODE.items()}


def contract_symbol(root: str, year: int, month: int) -> str:
    return f"{root}{MONTH_CODE[month]}{year % 100:02d}.{PRODUCTS[root]['suffix']}"


def contract_month_anchor(symbol: str) -> pd.Timestamp:
    """Return the contract delivery-month end encoded in a standard Yahoo futures symbol.

    This is not claimed to be the exchange's exact last-trade timestamp. It is a transparent
    ordering/tenor anchor when Yahoo omits ``expireDate``; exact-expiry-sensitive trading remains
    blocked pending an authoritative contract calendar.
    """
    match = re.match(r"^[A-Z]+([FGHJKMNQUVXZ])(\d{2})\.", symbol)
    if not match or match.group(1) not in CODE_MONTH:
        return pd.NaT
    month, year = CODE_MONTH[match.group(1)], 2000 + int(match.group(2))
    return pd.Timestamp(year=year, month=month, day=1, tz="UTC") + pd.offsets.MonthEnd(0)


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


def held_panels(out: Path = OUT) -> list[dict]:
    """The curve panels already on disk, left exactly as they are: name, rows, last date."""
    rows = []
    for path in sorted(out.glob("*_curve.parquet")) if out.exists() else []:
        try:
            frame = pd.read_parquet(path)
            last = frame["date"].max() if "date" in frame.columns else None
            rows.append({"file": path.name, "rows": int(len(frame)),
                         "last_date": None if last is None or pd.isna(last) else str(last),
                         "source_class": (str(frame["source_class"].iloc[0])
                                          if "source_class" in frame.columns and len(frame)
                                          else "UNLABELLED")})
        except Exception as exc:
            rows.append({"file": path.name, "error": type(exc).__name__})
    return rows


def main(argv: list[str] | None = None) -> int:
    """Write the refusal record. Opens no socket and never touches a held panel."""
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Yahoo delayed contract quotes -- REFUSED ON TERMS, not fetched",
        "source_id": SOURCE_ID,
        "source_class": source_class(),
        "blocked_on_terms": YAHOO_TERMS,
        "missed_growth": MISSED_GROWTH,
        "requests_made": 0,
        "contracts": [],
        "held_panels": held_panels(),
        "usable_curve_dates": 0,
        "promotion_authority": False,
        "status": "BLOCKED_ON_TERMS",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  {YAHOO_TERMS}; held panels left as they are, nothing fetched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
