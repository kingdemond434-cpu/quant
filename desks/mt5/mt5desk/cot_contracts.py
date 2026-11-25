"""ONE TABLE: which CFTC contract speaks for which MT5 instrument.

WHY THIS EXISTS (measured on 013f0b3f76). Three readers each held their own, shorter, spelling:

  * `mt5desk.data._SYMBOL_SLUG`      20 symbols -> the raw per-contract parquet the four raw COT
                                     families read. 1,428 cells (comm_follow 608, change_fade 493,
                                     change_momentum 241, net_fade 122) probed `cot_mapping`.
  * `scripts/refresh_cot_zcache.py`  11 symbols -> the z-score cache `cot_positioning` reads.
                                     1,411 cells probed `cot_series:<SYM>`.
  * `mt5desk.fetch_cot.TARGETS`      12 contracts fetched, and `eur.parquet` never landed, so 36
                                     more cells probed `cot_file:eur.parquet`.

Pure data, no imports beyond the standard library, so the fetcher, the zcache builder, the probe and
the tests all read the SAME rows.

NO CODE IS INVENTED. Every market name below is spelled exactly as the CFTC's own feed spells it in
`desks/mt5/data/observables/cftc_cot_live.json` (the repository's committed copy of dataset
6dca-aqww), or is a name/code `libs/data/cot_source.COT_MAP` and `scripts/refresh_cot_zcache.NEEDLES`
already carry. A test pins every `MARKETS` value against that file. A symbol whose contract is not
there is NOT mapped; `UNMAPPED` lists each with the reason.

EXOTICS ARE NEVER MAPPED: a fiat leg outside USD, EUR, JPY, GBP, CHF, AUD, NZD and CAD is out.
"""
from __future__ import annotations

#: The seven non-USD fiat legs that have a CME currency future, and the market name of each.
FX_LEG_MARKETS: dict[str, str] = {
    "EUR": "EURO FX - CHICAGO MERCANTILE EXCHANGE",
    "GBP": "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE",
    "AUD": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
    "NZD": "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE",
    "JPY": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
    "CHF": "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE",
    "CAD": "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
}
#: Currencies a pair may be built from. Anything else is an exotic and is never minted.
ALLOWED_FIAT = ("USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD")

#: The Fusion non-exotic FX pairs on the desk's registry (`data/universe/universe.json`).
FX_PAIRS: tuple[str, ...] = (
    "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD", "CADCHF", "CADJPY", "CHFJPY", "EURAUD",
    "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURNZD", "EURUSD", "GBPAUD", "GBPCAD", "GBPCHF",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCAD", "NZDCHF", "NZDJPY", "NZDUSD", "USDCAD", "USDCHF",
    "USDJPY",
)


def fx_legs(symbol: str) -> tuple[str, str] | None:
    """(base, quote) for a pair made only of ALLOWED_FIAT legs, else None. Names only."""
    s = str(symbol or "")
    if len(s) != 6 or not s.isalpha() or not s.isupper():
        return None
    b, q = s[:3], s[3:]
    if b == q or b not in ALLOWED_FIAT or q not in ALLOWED_FIAT:
        return None
    return b, q


#: slug -> exact CFTC market name, for the contracts the legacy fetcher cannot reach by
#: `commodity_name`. Every name is verbatim from the committed CFTC feed copy.
MARKETS: dict[str, str] = {
    **{ccy.lower(): name for ccy, name in FX_LEG_MARKETS.items()},
    "platinum": "PLATINUM - NEW YORK MERCANTILE EXCHANGE",
    "palladium": "PALLADIUM - NEW YORK MERCANTILE EXCHANGE",
    "brent": "BRENT LAST DAY - NEW YORK MERCANTILE EXCHANGE",
    "natgas": "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE",
    "copper": "COPPER- #1 - COMMODITY EXCHANGE INC.",
    "us30": "DJIA x $5 - CHICAGO BOARD OF TRADE",
    "us2000": "RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE",
    "jpn225": "NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE",
    "ust10y": "UST 10Y NOTE - CHICAGO BOARD OF TRADE",
    "ust5y": "UST 5Y NOTE - CHICAGO BOARD OF TRADE",
    "sugar": "SUGAR NO. 11 - ICE FUTURES U.S.",
    "coffee": "COFFEE C - ICE FUTURES U.S.",
    "cotton": "COTTON NO. 2 - ICE FUTURES U.S.",
    "corn": "CORN - CHICAGO BOARD OF TRADE",
    "soybeans": "SOYBEANS - CHICAGO BOARD OF TRADE",
    "wheat": "WHEAT-SRW - CHICAGO BOARD OF TRADE",
    "oj": "FRZN CONCENTRATED ORANGE JUICE - ICE FUTURES U.S.",
    "cocoa": "COCOA - ICE FUTURES U.S.",
    "btc": "BITCOIN - CHICAGO MERCANTILE EXCHANGE",
    "eth": "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE",
}
#: A contract the repository already addresses by its CFTC code (`libs/data/cot_source.COT_MAP`).
CODES: dict[str, str] = {"wti": "067411"}

#: slugs whose raw parquet the LEGACY fetcher already wrote (by `commodity_name`); unchanged.
LEGACY_SLUGS = ("gold", "silver", "jpy", "eur", "gbp", "cad", "aud", "nzd", "chf", "dxy",
                "sp500", "nasdaq100")

#: MT5 symbol -> raw-file slug. The long-standing rule is kept: a pair trades its base-currency
#: future, a JPY-quoted cross uses the yen, USD-based pairs use the other leg. SIGN is the
#: consumer's (the raw files hold the future's own long/short, un-inverted for USDxxx).
SYMBOL_SLUG: dict[str, str] = {
    "XAUUSD": "gold", "XAGUSD": "silver", "XAUEUR": "gold", "XAUAUD": "gold",
    "XAGEUR": "silver", "XPTUSD": "platinum", "XPDUSD": "palladium",
    "XTIUSD": "wti", "XBRUSD": "brent", "XNGUSD": "natgas", "XCUUSD": "copper",
    "DXY": "dxy", "USDX": "dxy", "SP500": "sp500", "NDX": "nasdaq100",
    "US500": "sp500", "NAS100": "nasdaq100", "US30": "us30", "US2000": "us2000",
    "JPN225": "jpn225", "UST10Y": "ust10y", "UST05Y": "ust5y",
    "SUGARRAW": "sugar", "COFARA": "coffee", "COTTON": "cotton", "CORN": "corn",
    "SOYBEAN": "soybeans", "WHEAT": "wheat", "OJ": "oj", "USCOCOA": "cocoa",
    "BTCUSD": "btc", "ETHUSD": "eth",
}
for _p in FX_PAIRS:
    _b, _q = fx_legs(_p)  # type: ignore[misc]
    SYMBOL_SLUG[_p] = (_q if _q == "JPY" else (_b if _b != "USD" else _q)).lower()

#: MT5 symbol -> the symbol whose zcache column it shares (the same underlying future).
ZCACHE_ALIAS: dict[str, str] = {"XAUEUR": "XAUUSD", "XAUAUD": "XAUUSD", "XAGEUR": "XAGUSD"}

#: zcache column -> exact market name(s) of a DIRECT (non-FX-cross) contract NOT in the original
#: eleven. These are backfilled in full the first run they are missing. Name drift is real (the
#: CFTC renamed some contracts), so a column holds the history of the CURRENT name only and the
#: reader's own 52-week floor decides whether that is enough.
ZCACHE_DIRECT: dict[str, tuple[str, ...]] = {
    "NZDUSD": (FX_LEG_MARKETS["NZD"],),
    "XBRUSD": (MARKETS["brent"],), "XNGUSD": (MARKETS["natgas"],),
    "XCUUSD": (MARKETS["copper"],),
    "US500": ("E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",),
    "NAS100": ("NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE",),
    "US30": (MARKETS["us30"],), "US2000": (MARKETS["us2000"],),
    "JPN225": (MARKETS["jpn225"],), "USDX": ("USD INDEX - ICE FUTURES U.S.",),
    "UST10Y": (MARKETS["ust10y"],), "UST05Y": (MARKETS["ust5y"],),
    "SUGARRAW": (MARKETS["sugar"],), "COFARA": (MARKETS["coffee"],),
    "COTTON": (MARKETS["cotton"],), "CORN": (MARKETS["corn"],),
    "SOYBEAN": (MARKETS["soybeans"],), "WHEAT": (MARKETS["wheat"],),
    "OJ": (MARKETS["oj"],), "USCOCOA": (MARKETS["cocoa"],),
    "BTCUSD": (MARKETS["btc"],), "ETHUSD": (MARKETS["eth"],),
}

#: Instruments with NO usable CFTC contract, so deliberately unmapped (never guessed).
UNMAPPED: dict[str, str] = {
    "USDHKD": "HKD is outside the allowed fiat legs (exotic)",
    "SUGAR": "unclear whether Fusion's SUGAR is white #5 (London) or raw #11; no CFTC white-sugar "
             "contract; left unmapped rather than spliced onto SUGAR NO. 11",
    "COFROB": "robusta is an ICE Europe contract; no CFTC contract",
    "UKCOCOA": "London cocoa is an ICE Europe contract; no CFTC contract",
    "UKGILT": "no CFTC contract (UK gilt futures are ICE Europe)",
    "XNIUSD": "LME nickel: no CFTC contract", "XPBUSD": "LME lead: no CFTC contract",
    "XZNUSD": "LME zinc: no CFTC contract", "XALUSD": "LME aluminium: no CFTC contract "
    "(the CFTC feed carries only an EURO PREM duty-paid contract, a different thing)",
    "AUS200": "ASX SPI is not a CFTC-reported contract", "CA60": "no CFTC contract",
    "CHINAH": "no CFTC contract", "E35": "no CFTC contract", "EUSTX50": "no CFTC contract",
    "FRA40": "no CFTC contract", "GER40": "no CFTC contract", "HK50": "no CFTC contract",
    "NETH25": "no CFTC contract", "UK100": "no CFTC contract",
    "ADAUSD": "no CFTC contract", "AVAXUSD": "no CFTC contract", "BCHUSD": "no CFTC contract "
    "in the committed feed (only perp-style Coinbase rows)", "BNBUSD": "no CFTC contract",
    "DOGEUSD": "no CFTC contract", "DOTUSD": "no CFTC contract", "EOSUSD": "no CFTC contract",
    "LNKUSD": "no CFTC contract", "LTCUSD": "no CFTC contract", "MATICUSD": "no CFTC contract",
    "SOLUSD": "SOL - CHICAGO MERCANTILE EXCHANGE exists in the feed but was not added: this "
              "change maps BTC and ETH only", "XLMUSD": "no CFTC contract (perp-style only)",
}
