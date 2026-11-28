"""CFTC Commitment of Traders (COT) miner.

Scrapes CFTC weekly COT reports for institutional positioning in
currency futures. When commercials (hedgers) are heavily positioned
one way, reversals often follow.

COT data is published every Friday at 3:30 ET for the prior Tuesday.
Uses positional parsing (no headers in the CFTC text file).
"""

from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "cot"
OUT.mkdir(parents=True, exist_ok=True)

COT_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
HEADERS = {"User-Agent": "quant-desk-research/1.0 (CFTC open data)"}

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


#: Weeks of history behind each z-score (three years), and the |z| that marks an extreme.
Z_WEEKS, Z_EXTREME, Z_SHIFT = 156, 2.0, 2.0


def _socrata_rows(fetch=None) -> list[dict]:
    """Positioning rows from the CFTC Public Reporting legacy futures-only dataset, one per symbol
    and week, plus the z-score of net speculator share against its own three years.

    THE ROUTE MOVED FROM www.cftc.gov/dea/newcot/FinFutWk.txt (2026-11-13). That file is the
    Traders in Financial Futures report: no metals, and dealer / asset-manager columns that the
    positional parser above read as non-commercial / commercial. publicreporting.cftc.gov is the
    CFTC's own open-data API (robots allows /resource/), carries the legacy categories the
    signals are named for, and covers gold, silver, platinum, palladium and WTI as well."""
    import sys as _sys
    _root = str(BASE.parent.parent)
    if _root not in _sys.path:
        _sys.path.append(_root)
    from libs.data import cot_source as C
    get = fetch or C.fetch_net_spec
    out: list[dict] = []
    for sym, (code, sign) in C.COT_MAP.items():
        try:
            net = get(code)
        except Exception as e:                      # one contract never kills the rest
            print(f"  COT {sym}: {type(e).__name__}")
            continue
        if net is None or len(net) < 60:
            continue
        net = (net * sign).iloc[-(Z_WEEKS + 2):]
        hist = net.iloc[:-1]
        sd = float(hist.std())
        if not sd or sd != sd:
            continue
        z = (float(net.iloc[-1]) - float(hist.mean())) / sd
        dz = (float(net.iloc[-1]) - float(net.iloc[-2])) / sd
        out.append({"symbol": sym, "date": net.index[-1].date().isoformat(),
                    "spec_net_share": round(float(net.iloc[-1]), 4), "z": round(z, 2),
                    "dz": round(dz, 2), "weeks": len(net)})
    return out


def mine_cot(fetch=None) -> list[dict]:
    """Positioning state for every mapped symbol, and a signal row where it is extreme or moved."""
    discoveries: list[dict] = []
    for r in _socrata_rows(fetch):
        sym, z, dz = r["symbol"], r["z"], r["dz"]
        discoveries.append({"source": "cot", "type": "positioning", "symbols": [sym], **r,
                            "description": f"{sym} spec net {r['spec_net_share']:+.1%} of OI, "
                                           f"z={z:+.1f} vs 3y"})
        if abs(z) >= Z_EXTREME:
            crowd = "long" if z > 0 else "short"
            discoveries.append({
                "source": "cot", "type": "extreme_positioning", "symbol": sym, "symbols": [sym],
                "z": z, "direction": crowd, "contrarian_signal": "short" if z > 0 else "long",
                "confidence": round(min(0.8, abs(z) / 4), 3), "date": r["date"],
                "description": f"Speculators crowded {crowd} {sym} (z={z:+.1f} vs 3y): "
                               f"contrarian reversal hypothesis"})
        if abs(dz) >= Z_SHIFT:
            way = "increasing" if dz > 0 else "decreasing"
            discoveries.append({
                "source": "cot", "type": "positioning_shift", "symbol": sym, "symbols": [sym],
                "dz": dz, "direction": way, "confidence": round(min(0.6, abs(dz) / 4), 3),
                "date": r["date"],
                "description": f"{sym} speculator share {way} by {abs(dz):.1f} sd in one week"})
    print(f"  COT: {len(discoveries)} rows")
    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_cot()
    out_file = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"cot: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
