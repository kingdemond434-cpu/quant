"""ONE symbol mapper for every retail-crowd source: a broker's ticker to the desk's universe name.

Copy-trade portfolios (MQL5 signals, FX Blue, Myfxbook) report the ticker of whatever broker the
account trades at: `EURUSD.x`, `XAUUSDm`, `GOLD`, `US30.cash`, `USTEC`, `DE40`, `BTCUSDT`. A crowd
net is only a crowd net when those rows land on ONE name, so the mapping lives here and every
crowd producer imports it (the A1 retail FX recorder and the A2 copy-trade aggregator share it).

    from libs.data.crowd_symbols import canonical
    canonical("XAUUSDm")      # 'XAUUSD'
    canonical("US30.cash")    # 'US30'
    canonical("Apple")        # None unless the universe carries it

`canonical` returns None for anything it cannot place: an unmapped ticker is counted by the
caller as unmapped, never guessed onto a near neighbour.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

UNIVERSE = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "universe"
            / "universe.json")

#: Broker aliases for the same economic instrument. Keys are upper-case with punctuation removed.
ALIASES: dict[str, str] = {
    "GOLD": "XAUUSD", "XAU": "XAUUSD", "GOLDUSD": "XAUUSD",
    "SILVER": "XAGUSD", "XAG": "XAGUSD", "SILVERUSD": "XAGUSD",
    "PLATINUM": "XPTUSD", "PALLADIUM": "XPDUSD", "COPPER": "XCUUSD", "HGCOPPER": "XCUUSD",
    "US30": "US30", "DJ30": "US30", "DJI30": "US30", "WS30": "US30", "DOW": "US30",
    "DOWJONES": "US30", "YM": "US30", "USA30": "US30", "DJ": "US30",
    "NAS100": "NAS100", "NAS": "NAS100", "USTEC": "NAS100", "US100": "NAS100", "NDX": "NAS100",
    "NQ": "NAS100", "NDX100": "NAS100", "NASDAQ": "NAS100", "NASDAQ100": "NAS100",
    "USA100": "NAS100", "USTECH": "NAS100", "TECH100": "NAS100",
    "US500": "US500", "SPX500": "US500", "SP500": "US500", "SPX": "US500", "USA500": "US500",
    "ES": "US500", "US2000": "US2000", "RUSSELL2000": "US2000", "RTY": "US2000",
    "GER40": "GER40", "GER30": "GER40", "DE40": "GER40", "DE30": "GER40", "DAX": "GER40",
    "DAX40": "GER40", "GERMANY40": "GER40", "UK100": "UK100", "FTSE100": "UK100",
    "FTSE": "UK100", "JPN225": "JPN225", "JP225": "JPN225", "NIKKEI": "JPN225",
    "NIKKEI225": "JPN225", "JAPAN225": "JPN225", "FRA40": "FRA40", "CAC40": "FRA40",
    "F40": "FRA40", "EUSTX50": "EUSTX50", "STOXX50": "EUSTX50", "EU50": "EUSTX50",
    "ESTX50": "EUSTX50", "HK50": "HK50", "HSI": "HK50", "HK33": "HK50", "AUS200": "AUS200",
    "ASX200": "AUS200", "AU200": "AUS200", "ESP35": "E35", "SPA35": "E35", "IBEX35": "E35",
    "CHINAH": "CHINAH", "CHINA50": "CHINAH",
    "USOIL": "XTIUSD", "WTI": "XTIUSD", "CRUDE": "XTIUSD", "CL": "XTIUSD", "OILUSD": "XTIUSD",
    "XTI": "XTIUSD", "USCRUDE": "XTIUSD", "UKOIL": "XBRUSD", "BRENT": "XBRUSD",
    "XBR": "XBRUSD", "NATGAS": "XNGUSD", "NGAS": "XNGUSD", "XNG": "XNGUSD", "NG": "XNGUSD",
    "BTCUSDT": "BTCUSD", "BITCOIN": "BTCUSD", "XBTUSD": "BTCUSD", "ETHUSDT": "ETHUSD",
    "ETHEREUM": "ETHUSD", "SOLUSDT": "SOLUSD", "DXY": "USDX", "USDINDEX": "USDX",
}

#: Broker suffixes and prefixes that decorate a ticker without changing the instrument.
_SUFFIXES = ("MICRO", "MINI", "CASH", "SPOT", "ECN", "PRO", "RAW", "STD", "STP", "VIP", "ZERO",
             "PLUS", "FX", "M", "I", "C", "Z", "X", "E", "R", "B", "S", "A", "N", "P", "Q")
_NON_ALNUM = re.compile(r"[^A-Z0-9]")


@lru_cache(maxsize=1)
def universe() -> frozenset[str]:
    try:
        doc = json.loads(UNIVERSE.read_text(encoding="utf-8-sig"))
        return frozenset(str(k).upper() for k in doc) if isinstance(doc, dict) else frozenset()
    except (OSError, ValueError):
        return frozenset()


def _known(name: str, uni: frozenset[str]) -> str | None:
    if name in ALIASES:
        return ALIASES[name]
    if name in uni:
        return name
    return None


def canonical(raw: object, uni: frozenset[str] | None = None) -> str | None:
    """The universe name of a broker ticker, or None when it cannot be placed honestly."""
    u = universe() if uni is None else frozenset(x.upper() for x in uni)
    s = str(raw or "").strip().upper()
    if not s:
        return None
    # A dotted or underscored decoration is never part of the instrument: EURUSD.x, US30_cash.
    head = re.split(r"[._#+\-/ ]", s, maxsplit=1)[0]
    for cand in (s, head):
        name = _NON_ALNUM.sub("", cand)
        hit = _known(name, u)
        if hit:
            return hit
        # Trailing broker decorations, peeled one at a time: XAUUSDM, EURUSDPRO, US30CASH.
        cur = name
        for _ in range(3):
            for suf in _SUFFIXES:
                if len(cur) > len(suf) + 2 and cur.endswith(suf):
                    cur = cur[: -len(suf)]
                    hit = _known(cur, u)
                    if hit:
                        return hit
                    break
            else:
                break
        # A six-letter currency pair followed by anything: EURUSDMICRO2 -> EURUSD.
        if len(name) > 6 and name[:6].isalpha():
            hit = _known(name[:6], u)
            if hit:
                return hit
    return None
