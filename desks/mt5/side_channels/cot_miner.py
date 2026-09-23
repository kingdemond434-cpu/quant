"""CFTC Commitment of Traders (COT) miner.

Scrapes CFTC weekly COT reports for institutional positioning in
currency futures. When commercials (hedgers) are heavily positioned
one way, reversals often follow.

COT data is published every Friday at 3:30 ET for the prior Tuesday.
Uses positional parsing (no headers in the CFTC text file).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "cot"
OUT.mkdir(parents=True, exist_ok=True)

COT_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

# Map CFTC contract names to our symbols
CONTRACT_MAP = {
    "CANADIAN DOLLAR": "USDCAD",
    "EURO FX": "EURUSD",
    "JAPANESE YEN": "USDJPY",
    "BRITISH POUND": "GBPUSD",
    "SWISS FRANC": "USDCHF",
    "AUSTRALIAN DOLLAR": "AUDUSD",
    "NZ DOLLAR": "NZDUSD",
    "MEXICAN PESO": "USDMXN",
    "GOLD": "XAUUSD",
    "SILVER": "XAGUSD",
    "MICRO GOLD": "XAUUSD",
    "MICRO SILVER": "XAGUSD",
}

# COT positional fields (0-indexed from the CFTC text format)
# [0] = contract name, [1] = date (YYMMDD), [2] = date (YYYY-MM-DD)
# [6] = open interest
# [7] = non-comm long, [8] = non-comm short
# [13] = comm long, [14] = comm short
# [19] = non-rept long, [20] = non-rept short
IDX_CONTRACT = 0
IDX_DATE = 2
IDX_OI = 6
IDX_NC_LONG = 7
IDX_NC_SHORT = 8
IDX_COMM_LONG = 13
IDX_COMM_SHORT = 14


def _parse_cot(text: str) -> list[dict]:
    """Parse CFTC positional text format."""
    lines = text.strip().split("\n")
    records = []

    for line in lines[1:]:  # skip header
        if not line.strip():
            continue
        fields = line.split(",")
        if len(fields) < 15:
            continue

        name = fields[IDX_CONTRACT].strip().strip('"')
        date = fields[IDX_DATE].strip()

        # Match to our symbols
        matched_sym = None
        for contract, sym in CONTRACT_MAP.items():
            if contract in name.upper():
                matched_sym = sym
                break
        if not matched_sym:
            continue

        try:
            oi = int(fields[IDX_OI].strip() or "0")
            nc_long = int(fields[IDX_NC_LONG].strip() or "0")
            nc_short = int(fields[IDX_NC_SHORT].strip() or "0")
            comm_long = int(fields[IDX_COMM_LONG].strip() or "0")
            comm_short = int(fields[IDX_COMM_SHORT].strip() or "0")

            if oi == 0:
                continue

            nc_net = nc_long - nc_short
            comm_net = comm_long - comm_short
            spec_pct = nc_net / oi * 100
            comm_pct = comm_net / oi * 100

            records.append({
                "source": "cot",
                "type": "positioning",
                "symbol": matched_sym,
                "contract": name,
                "date": date,
                "open_interest": oi,
                "non_commercial_long": nc_long,
                "non_commercial_short": nc_short,
                "non_commercial_net": nc_net,
                "commercial_long": comm_long,
                "commercial_short": comm_short,
                "commercial_net": comm_net,
                "spec_pct_of_oi": round(spec_pct, 2),
                "comm_pct_of_oi": round(comm_pct, 2),
            })
        except (ValueError, IndexError):
            continue

    return records


def _detect_extremes(records: list[dict]) -> list[dict]:
    """Detect positioning extremes that signal reversals."""
    signals = []
    by_sym = {}
    for r in records:
        by_sym.setdefault(r["symbol"], []).append(r)

    for sym, data in by_sym.items():
        if len(data) < 2:
            continue
        latest = data[-1]
        prev = data[-2]

        spec_pct = latest["spec_pct_of_oi"]
        spec_change = spec_pct - prev["spec_pct_of_oi"]

        if abs(spec_pct) > 30:
            direction = "long" if spec_pct > 0 else "short"
            signals.append({
                "source": "cot",
                "type": "extreme_positioning",
                "symbol": sym,
                "spec_pct": spec_pct,
                "direction": direction,
                "contrarian_signal": "short" if spec_pct > 30 else "long",
                "confidence": min(0.8, abs(spec_pct) / 50),
                "description": f"Speculators {abs(spec_pct):.1f}% net {direction} - contrarian reversal signal",
            })

        if abs(spec_change) > 10:
            direction = "increasing" if spec_change > 0 else "decreasing"
            signals.append({
                "source": "cot",
                "type": "positioning_shift",
                "symbol": sym,
                "spec_change": round(spec_change, 2),
                "direction": direction,
                "confidence": min(0.6, abs(spec_change) / 20),
                "description": f"Speculator positioning {direction} by {abs(spec_change):.1f}% in one week",
            })

    return signals


def mine_cot() -> list[dict]:
    """Fetch and analyze COT data."""
    discoveries = []
    try:
        resp = requests.get(COT_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        records = _parse_cot(resp.text)
        print(f"  COT: {len(records)} records parsed")
        discoveries.extend(records)

        extremes = _detect_extremes(records)
        if extremes:
            print(f"  COT extremes: {len(extremes)} signals")
            discoveries.extend(extremes)

    except Exception as e:
        print(f"  COT failed: {e}")

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_cot()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"cot: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
