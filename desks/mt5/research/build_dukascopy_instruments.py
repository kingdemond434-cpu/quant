"""Build `data/dukascopy_instruments.json`: every Fusion symbol -> its Dukascopy instrument.

WHY A GENERATED DATA FILE AND NOT A LONGER `POINT` TABLE. `fetch_dukascopy.POINT` covers 35
symbols and five of them were never Dukascopy instrument ids at all: the feed has no `XTIUSD`,
`XBRUSD`, `XNGUSD`, `XPTUSD` or `XPDUSD` (it publishes LIGHT.CMD/USD, BRENT.CMD/USD, GAS.CMD/USD,
XPT.CMD/USD and XPD.CMD/USD), so every hour of those five returned 404, was recorded as "missing",
and the backfill published an EMPTY day and advanced its cursor. GAS.CMD/USD's factor is also
10,000, not the 1,000 POINT carries. A hand-typed table drifts; this one is DERIVED from the
vendor's own published metadata and every row cites it.

THE SOURCE, PINNED. The open-source `dukascopy-node` project publishes, per instrument, the id
the datafeed URL uses and the `decimalFactor` its integer prices are scaled by:

    https://raw.githubusercontent.com/Leo4815162342/dukascopy-node/
        4bb92bcbcd2edf7c7d75783173f1dae40bee7ef4/
        src/utils/instrument-meta-data/generated/instrument-meta-data.json

That commit is the git head of npm release dukascopy-node@1.46.4 (2026-03-09), the LAST release
whose metadata carries `decimalFactor`. From 1.49 the project reads a per-response multiplier
from a JSON endpoint instead, and its metadata file no longer states a factor; the bi5 datafeed
this desk reads is unchanged, so the last published static factor is the authority here.

NO FACTOR IS GUESSED. A Fusion symbol maps only when (a) its name IS a vendor FX/metal/crypto
pair id, or (b) a curated alias below names a vendor id that exists in the pinned file and whose
vendor description is the same underlying. Everything else is written as UNMAPPED with a reason,
and the fetcher refuses it exactly as it refused unknown symbols before. Different underlyings
are never bridged by "close enough": China A50 is not the Hang Seng China Enterprises index, the
30-year T-bond is not the 5- or 10-year note, and NY cocoa is not London cocoa.

    python research/build_dukascopy_instruments.py                 # fetch the pinned file
    python research/build_dukascopy_instruments.py --meta FILE      # offline, from a local copy
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
UNIVERSE = BASE / "data" / "universe" / "universe.json"
OUT = BASE / "data" / "dukascopy_instruments.json"

SOURCE_REPO = "https://github.com/Leo4815162342/dukascopy-node"
SOURCE_COMMIT = "4bb92bcbcd2edf7c7d75783173f1dae40bee7ef4"
SOURCE_RELEASE = "dukascopy-node@1.46.4"
SOURCE_PATH = "src/utils/instrument-meta-data/generated/instrument-meta-data.json"
SOURCE_URL = (f"https://raw.githubusercontent.com/Leo4815162342/dukascopy-node/"
              f"{SOURCE_COMMIT}/{SOURCE_PATH}")

# Fusion symbol -> (vendor metadata key, why it is the same underlying). Only non-mechanical
# names live here; an FX, metal or crypto pair whose Fusion name equals the vendor id maps itself.
ALIASES: dict[str, tuple[str, str]] = {
    # energy and metals quoted under the vendor's .CMD ids
    "XTIUSD": ("lightcmdusd", "WTI crude = US Light Crude Oil"),
    "XBRUSD": ("brentcmdusd", "Brent crude"),
    "XNGUSD": ("gascmdusd", "US natural gas"),
    "XPTUSD": ("xptcmdusd", "platinum"),
    "XPDUSD": ("xpdcmdusd", "palladium"),
    "XCUUSD": ("coppercmdusd", "high-grade copper"),
    "MATICUSD": ("matusd", "Polygon (MATIC) vs US dollar"),
    # equity indices
    "US500": ("usa500idxusd", "S&P 500"),
    "US30": ("usa30idxusd", "Dow Jones Industrial Average"),
    "NAS100": ("usatechidxusd", "Nasdaq 100"),
    "US2000": ("ussc2000idxusd", "Russell 2000 (US Small Cap 2000)"),
    "GER40": ("deuidxeur", "DAX 40"),
    "FRA40": ("fraidxeur", "CAC 40"),
    "UK100": ("gbridxgbp", "FTSE 100"),
    "EUSTX50": ("eusidxeur", "Euro Stoxx 50"),
    "E35": ("espidxeur", "IBEX 35"),
    "NETH25": ("nldidxeur", "AEX 25"),
    "JPN225": ("jpnidxjpy", "Nikkei 225"),
    "AUS200": ("ausidxaud", "ASX 200"),
    "HK50": ("hkgidxhkd", "Hang Seng (vendor 'Hong Kong 40 Index')"),
    "USDX": ("dollaridxusd", "US Dollar Index"),
    # bonds
    "UKGILT": ("ukgilttrgbp", "UK Long Gilt future"),
    # soft commodities
    "COFARA": ("coffeecmdusx", "Coffee Arabica, US cents"),
    "COTTON": ("cottoncmdusx", "Cotton No.2, US cents"),
    "OJ": ("ojuicecmdusx", "frozen concentrated orange juice, US cents"),
    "SOYBEAN": ("soybeancmdusx", "soybeans, US cents"),
    "SUGAR": ("sugarcmdusd", "London (white) sugar No.5, USD/t"),
    "USCOCOA": ("cocoacmdusd", "NY cocoa"),
}

# Single-name equities: Fusion's display name -> US ticker. The vendor id is <TICKER>.US/USD.
# These are COLLECTED (bars and ticks are still collected for share CFDs, CLAUDE.md two-lane
# order); they are never hunted for statistical hypotheses here or anywhere.
EQUITY_TICKERS: dict[str, str] = {
    "3M": "MMM", "ADP": "ADP", "AMD": "AMD", "AT&T": "T", "Accenture": "ACN", "Adobe": "ADBE",
    "Airbnb": "ABNB", "AlibabaGroup": "BABA", "Alphabet-A": "GOOGL", "Alphabet-C": "GOOG",
    "Amazon": "AMZN", "AmericanExpress": "AXP", "Amgen": "AMGN", "Apple": "AAPL",
    "AppliedMaterials": "AMAT", "Atlassian": "TEAM", "Baidu": "BIDU",
    "BankofAmericaCorp": "BAC", "Berkshire": "BRKB", "BlackRock": "BLK", "Boeing": "BA",
    "Booking": "PCLN", "Broadcom": "AVGO", "CVSHealth": "CVS", "Caterpillar": "CAT",
    "CharlesSchwab": "SCHW", "Charter": "CHTR", "Chevron": "CVX", "Cisco": "CSCO",
    "Citigroup": "C", "Coca-Cola": "KO", "Coinbase": "COIN", "Comcast": "CMCSA",
    "CostcoWholesale": "COST", "DocuSign": "DOCU", "Doordash": "DASH", "Dow": "DOW",
    "ElectronicArts": "EA", "ExxonMobil": "XOM", "Ford": "F", "GeneralElectric": "GE",
    "GeneralMotors": "GM", "GileadSciences": "GILD", "GoldmanSachs": "GS", "HomeDepot": "HD",
    "Honeywell": "HON", "IBM": "IBM", "Intel": "INTC", "Intuit": "INTU",
    "IntuitiveSurgical": "ISRG", "JPMorganChase": "JPM", "Johnson&Johnson": "JNJ",
    "LucidGroup": "LCID", "Lyft": "LYFT", "Mastercard": "MA", "McDonalds": "MCD",
    "Medtronic": "MDT", "Merck": "MRK", "Meta": "FB", "MicronTechnology": "MU",
    "Microsoft": "MSFT", "MorganStanley": "MS", "NIO": "NIO", "NVIDIA": "NVDA",
    "Netflix": "NFLX", "Nike": "NKE", "Oracle": "ORCL", "PayPal": "PYPL", "Pepsi": "PEP",
    "Pfizer": "PFE", "PhilipMorrisInternational": "PM", "Pinterest": "PINS",
    "Procter&Gamble": "PG", "Qualcomm": "QCOM", "RobinhoodMarkets": "HOOD", "Roku": "ROKU",
    "S&PGlobal": "SPGI", "Salesforce": "CRM", "ServiceNow": "NOW", "Shopify": "SHOP",
    "Snapchat": "SNAP", "Snowflake": "SNOW", "Spotify": "SPOT", "Starbucks": "SBUX",
    "TMEGroup": "TME", "TSMC": "TSM", "Target": "TGT", "Tesla": "TSLA",
    "TexasInstruments": "TXN", "ThermoFisherScientific": "TMO", "Toyota": "TM",
    "Travelers": "TRV", "Twilio": "TWLO", "Uber": "UBER", "UnionPacific": "UNP",
    "UnitedHealth": "UNH", "UnitedParcelService": "UPS", "Verizon": "VZ", "Visa": "V",
    "Walmart": "WMT", "WaltDisney": "DIS", "WellsFargo": "WFC", "eBay": "EBAY",
    "BeyondMeat": "BYND", "BlockInc": "SQ", "Walgreens": "WBA",
}

# The same ISSUER under its pre-rename ticker: the vendor id predates the corporate rename, and the
# vendor's own description names the issuer. A rename moves no price scale.
EQUITY_RENAMES: dict[str, str] = {
    "Meta": "Facebook Inc renamed Meta Platforms (2021-22); vendor description "
            "'FACEBOOK INC-A / META'",
    "Booking": "Priceline Group renamed Booking Holdings (2018); vendor id PCLN",
    "BlockInc": "Square Inc renamed Block Inc (2021); vendor id SQ",
}

# Named reasons for the curated refusals, so the report says WHY rather than only "absent".
NOT_PUBLISHED: dict[str, str] = {
    "CHINAH": "vendor publishes China A50 (CHI.IDX), a different index from Hang Seng China "
              "Enterprises; not bridged",
    "CA60": "vendor publishes no S&P/TSX 60 instrument",
    "UST05Y": "vendor publishes only the 30-year USTBOND.TR; a 5-year note is a different "
              "duration, not bridged",
    "UST10Y": "vendor publishes only the 30-year USTBOND.TR; a 10-year note is a different "
              "duration, not bridged",
    "UKCOCOA": "vendor publishes NY cocoa only; London cocoa (GBP) is a different contract",
    "SUGARRAW": "vendor publishes London No.5 white sugar only; raw No.11 is a different contract",
    "COFROB": "vendor publishes Arabica only; Robusta is a different contract",
    "CORN": "vendor publishes no corn instrument",
    "WHEAT": "vendor publishes no wheat instrument",
    "XALUSD": "vendor publishes no aluminium instrument",
    "XNIUSD": "vendor publishes no nickel instrument",
    "XPBUSD": "vendor publishes no lead instrument",
    "XZNUSD": "vendor publishes no zinc instrument",
}


def _load_meta(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is not None:
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "quant-research/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _row(key: str, entry: dict[str, Any], asset_class: str, basis: str,
         note: str) -> dict[str, Any]:
    return {
        "vendor_key": key,
        # dukascopy-node requests `datafeed/${instrument.toUpperCase()}/...` with this key.
        "vendor_code": key.upper(),
        "vendor_name": entry["name"],
        "vendor_description": entry.get("description"),
        "decimal_factor": int(entry["decimalFactor"]),
        "start_hour_for_ticks": entry.get("startHourForTicks"),
        "asset_class": asset_class,
        "basis": basis,
        "note": note,
    }


def build(universe: dict[str, Any], meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mapped: dict[str, dict[str, Any]] = {}
    unmapped: dict[str, dict[str, Any]] = {}
    for symbol in sorted(universe):
        row = universe[symbol]
        if not isinstance(row, dict):
            continue
        asset_class = str(row.get("asset_class") or "UNCLASSIFIED")
        key: str | None = None
        basis = note = ""
        if symbol in ALIASES:
            key, note = ALIASES[symbol]
            basis = "curated_alias"
        elif symbol in EQUITY_TICKERS:
            key = f"{EQUITY_TICKERS[symbol].lower()}ususd"
            basis = "equity_ticker"
            note = EQUITY_RENAMES.get(symbol, f"US ticker {EQUITY_TICKERS[symbol]}")
        elif symbol.lower() in meta and "/" in str(meta[symbol.lower()].get("name", "")) \
                and "." not in str(meta[symbol.lower()]["name"]):
            key, basis, note = symbol.lower(), "identical_pair_id", "vendor pair id == Fusion name"
        entry = meta.get(key) if key else None
        if entry is None or not entry.get("decimalFactor"):
            if symbol in NOT_PUBLISHED:
                reason = NOT_PUBLISHED[symbol]
            elif key:
                reason = (f"no vendor instrument '{key}' with a decimalFactor in the pinned "
                          f"metadata ({note})")
            else:
                reason = "no vendor instrument of this name and no curated alias"
            unmapped[symbol] = {"asset_class": asset_class, "reason": reason}
            continue
        mapped[symbol] = _row(key or "", entry, asset_class, basis, note)
    return {
        "schema_version": 1,
        "authority": "RESEARCH_DEPTH_ONLY",
        "source": {"repo": SOURCE_REPO, "commit": SOURCE_COMMIT, "release": SOURCE_RELEASE,
                   "path": SOURCE_PATH, "url": SOURCE_URL,
                   "fields": "instrument id (datafeed path) and decimalFactor"},
        "generator": "desks/mt5/research/build_dukascopy_instruments.py",
        "mapped": mapped,
        "unmapped": unmapped,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", type=Path, default=None,
                    help="local copy of the pinned instrument-meta-data.json (offline build)")
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    universe = json.loads(args.universe.read_text(encoding="utf-8"))
    doc = build(universe, _load_meta(args.meta))
    tmp = args.out.with_suffix(args.out.suffix + ".partial")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    os.replace(tmp, args.out)
    print(f"{len(doc['mapped'])} mapped, {len(doc['unmapped'])} unmapped -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
