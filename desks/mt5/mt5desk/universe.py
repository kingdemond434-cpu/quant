"""Every instrument the broker actually offers, classified, with its real cost.

WHY THIS REPLACES A HARDCODED LIST

`fetch_universe.CANDIDATES` named 32 symbols by hand. Nine of them -- WTI, BRENT, USOIL, US500,
US30, USTEC, NAS100, SPX500, JP225 -- were simply not offered on the Vantage account, so the
energy and index complexes were absent from every hunt this desk has ever run, and the reason was
invisible: the fetcher printed "not offered" and moved on, and nothing downstream recorded that a
whole asset class had never been tested.

A hardcoded list also cannot survive a broker change. Moving Vantage -> Fusion changes both which
symbols exist AND what they are named (`US500` vs `SPX500` vs `USA500` are the same index at
three brokers), so the list would silently shrink at exactly the moment the desk was told to hunt
wider.

WHAT "TRADEABLE" MEANS HERE, AND WHY THE BAR IS LOW

This module deliberately does NOT decide what is worth trading. It answers "what exists, what is
it, and what does it cost", and admits anything with a real cost model and enough history to
backtest. Everything else -- whether the edge survives the spread -- is the battery's job, and
that job is done per-cell against measured cost rather than by excluding instruments up front on
a guess about liquidity.

The one lesson imported from the crypto desk's carry work: ranking a universe by GROSS
attractiveness selects for illiquidity, because a wide spread is the compensation for it. So
cost travels with every symbol from the moment of discovery, and no consumer is allowed to see a
candidate without it.

MULTIPLICITY IS THE PRICE OF BREADTH. Going from 22 symbols to the full offering multiplies the
cell count, and `mt5desk.multiplicity` raises the significance bar to match. Widening the search
without widening the correction manufactures survivors; the two must move together, and they do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: Asset class inferred from the symbol name. Deliberately pattern-based rather than a lookup
#: table: broker symbol sets change and a table would silently mark new instruments UNKNOWN.
_FX_MAJORS = ("EUR", "GBP", "USD", "JPY", "CHF", "CAD", "AUD", "NZD")
#: Non-major but liquid FX legs. A cross of two of these (NOKSEK) is still FX -- it read
#: "unknown" when the whole broker offering landed, because the old rules demanded a MAJOR leg.
_FX_MINORS = ("SEK", "NOK", "DKK", "SGD", "HKD", "MXN", "ZAR", "TRY", "PLN", "HUF", "CZK", "CNH")
_METALS = ("XAU", "XAG", "XPT", "XPD", "GOLD", "SILVER")
_ENERGY = ("WTI", "BRENT", "OIL", "NGAS", "NATGAS", "CRUDE", "UKOIL", "USOIL")
_CRYPTO = ("BTC", "ETH", "LTC", "XRP", "BCH", "ADA", "SOL", "DOGE", "DOT", "LINK",
           "AVAX", "MATIC", "XLM", "TRX", "UNI", "ATOM", "AAVE", "SHIB")
#: SOFT COMMODITIES and BONDS -- whole asset classes the broker lists that had no pattern here,
#: so they read "unknown" and sat outside every breadth count (2026-08-27, the 251-symbol
#: collection). They matter for the same reason equities do: cocoa responds to West African
#: weather and gilts to rate expectations, which is diversification a JPY cross cannot provide.
_SOFT = ("COTTON", "SOYBEAN", "SUGAR", "COCOA", "COFFEE", "COFARA", "COFROB", "WHEAT",
         "CORN", "ORANGE", "LUMBER", "CATTLE", "HOGS", "RICE", "OATS", "CANOLA")
_BOND = ("UST", "UKGILT", "GILT", "BUND", "BOBL", "SCHATZ", "OAT", "BTP", "JGB", "TNOTE")
_INDEX = ("US500", "US30", "USTEC", "NAS", "SPX", "SP500", "DAX", "GER", "UK100", "FTSE",
          "JP225", "JPN225", "NIK", "HK50", "AUS200", "EU50", "STOXX", "FRA40", "USA",
          "USDX", "EUSTX", "NETH", "CHINAH", "SWI", "ESP", "CA60", "E35")

#: Below this many bars a cell cannot be evaluated at all: the battery needs n > 60 trades, and
#: a session-window family fires on a fraction of days. 1,000 H1 bars is roughly six weeks of
#: 24/5 trading -- the floor at which a symbol is worth carrying, not a claim that it is enough.
MIN_BARS = 1000

# ============================ WHERE A TICKER ROOT IS ALLOWED TO END ============================
#
# THE DEFECT THIS CLOSES, measured on the trading box 2026-09-23 and again 2026-09-24. The root
# lists above were matched with a bare `startswith`/`in`, so a root that happened to be the first
# letters of an ENGLISH WORD claimed the whole instrument:
#
#     UnionPacific          -> crypto   ("UNI" = Uniswap, sitting in front of "on Pacific")
#     UnitedHealth          -> crypto   ("UNI" again)
#     UnitedParcelService   -> crypto   ("UNI" again)
#     GoldmanSachs          -> metal    ("GOLD" in front of "man Sachs")
#     Nike                  -> index    ("NIK" = Nikkei, inside "Nike")
#
# FIVE US SHARE CFDs IN THE HYPOTHESIS-DISCOVERY LANE, which the two-lane order (principal
# 2026-09-06) puts in the news/earnings lane instead -- and each of them spending trial budget
# that the deflated-Sharpe charge takes off every FX and metals cell. It is also wrong where no
# lane is involved: `libs/portfolio/robust_elog._asset_class` POOLS sleeves by this class for
# correlation shrinkage, so UnionPacific was borrowing BTCUSD's mean and GoldmanSachs was
# borrowing gold's -- the desk's only live book.
#
# The same shape had already been caught once, for bonds ("UST" inside "EUSTX50", 2026-08-28) and
# repaired by narrowing that ONE list to a prefix test. A prefix test is not the fix: "UNI" IS a
# prefix of "UnionPacific". The fix is a BOUNDARY: a ticker root identifies an instrument only
# when the symbol stops being a name at the point the root ends.
#
# Two independent tests, both required, because they fail on different kinds of symbol:
#
#   (a) THE NAME TEST. Broker CODES are upper-case; share CFDs arrive as CamelCase company names.
#       A root followed (or preceded) by a LOWER-CASE letter in the raw string is the first
#       letters of a word, not a ticker -- "Uni|onPacific", "Gold|manSachs", "Nik|e". This is the
#       word boundary in the literal sense, read off the case the broker already supplies.
#   (b) THE CODE TEST. In a broker code the root is followed by the thing it is quoted against or
#       by nothing at all: `XAU|USD`, `BTC|USD`, `GOLD`, `UST|05Y`, `GER|40`. Anything else is a
#       longer word that merely starts with the root. Applied to the PREFIX-rooted lists only --
#       the soft-commodity and index lists legitimately carry mid-symbol tokens (`UKCOCOA`,
#       `USCOCOA`) and legitimate trailing words (`SUGARRAW`), and (a) is what disciplines those.

#: Currency codes a broker code may be quoted against. Used ONLY to recognise the boundary at the
#: end of a ticker root; the FX rules below own the actual pair decomposition.
_QUOTE_CODES: tuple[str, ...] = tuple(sorted(set(_FX_MAJORS) | set(_FX_MINORS)))

#: `<ROOT>USD`, `<ROOT>EUR`, plus the short venue/contract suffix brokers bolt on (`.raw`, `m`,
#: `-ECN` -- the separators are already stripped by the time this is tested).
_CCY_TAIL = re.compile(r"(?:" + "|".join(_QUOTE_CODES) + r")[0-9A-Z]{0,4}")

#: `UST05Y`, `GER40`, `NETH25`, `US500CASH` -- a contract, expiry or index-level suffix. It must
#: START with a digit: that is what keeps a trailing WORD ("MANSACHS", "ONPACIFIC") out.
_CONTRACT_TAIL = re.compile(r"\d{1,4}[A-Z]{0,4}")


def _clean(symbol: str) -> tuple[str, tuple[int, ...]]:
    """Upper-cased alphanumerics of `symbol`, with each kept character's index in the RAW string.

    The indices are the whole point: the raw string carries the CASE, and the case is what says
    where one word ends and the next begins in a company name.
    """
    raw = str(symbol)
    chars: list[str] = []
    where: list[int] = []
    for i, ch in enumerate(raw):
        up = ch.upper()
        # `len(up) == 1` guards the characters whose upper-case is longer than themselves
        # ("ß" -> "SS"), which would desynchronise the index map it is built to keep honest.
        if len(up) == 1 and (("A" <= up <= "Z") or ("0" <= up <= "9")):
            chars.append(up)
            where.append(i)
    return "".join(chars), tuple(where)


def _at_word_boundary(raw: str, where: tuple[int, ...], start: int, length: int) -> bool:
    """True when the root occupying `cleaned[start:start+length]` is a WORD, not part of one.

    Test (a) above: a lower-case letter on either side of the match in the raw string means the
    root is the opening or middle of an English word -- "Uni|onPacific", "S|poi|ler" -- and a word
    is never a ticker. Reading the case rather than a list of exceptions is what makes this work
    for the share CFD the broker lists tomorrow.
    """
    before = raw[where[start] - 1] if start > 0 and where[start] > 0 else ""
    after = raw[where[start + length - 1] + 1:][:1]
    return not before.islower() and not after.islower()


def _tail_is_a_boundary(tail: str) -> bool:
    """Test (b) above: what follows a ticker root in a broker CODE, or nothing at all."""
    if not tail:
        return True
    return bool(_CCY_TAIL.fullmatch(tail) or _CONTRACT_TAIL.fullmatch(tail))


def _rooted(raw: str, cleaned: str, where: tuple[int, ...], roots: tuple[str, ...]) -> bool:
    """A root list matched at the START of the symbol, under BOTH boundary tests."""
    for root in roots:
        if cleaned.startswith(root) and _at_word_boundary(raw, where, 0, len(root)) \
                and _tail_is_a_boundary(cleaned[len(root):]):
            return True
    return False


def _tokened(raw: str, cleaned: str, where: tuple[int, ...], roots: tuple[str, ...]) -> bool:
    """A root list matched ANYWHERE in the symbol, under the word-boundary test only.

    Mid-symbol matching is load-bearing for these lists -- `UKCOCOA` and `USCOCOA` are the soft
    commodity, `EUSTX50` is the index -- so narrowing them to a prefix would delete real
    instruments. (a) is enough: it is company NAMES that produce the false positives here.
    """
    for root in roots:
        at = cleaned.find(root)
        while at >= 0:
            if _at_word_boundary(raw, where, at, len(root)):
                return True
            at = cleaned.find(root, at + 1)
    return False


def asset_class(symbol: str) -> str:
    """Best-effort class for `symbol`. Never raises; unknown is a REPORTED state, not a crash."""
    raw = str(symbol)
    s, where = _clean(raw)
    # Order matters: XAUUSD contains "USD" and would read as FX if FX were tested first.
    if _rooted(raw, s, where, _METALS):
        return "metal"
    if _rooted(raw, s, where, _CRYPTO):
        return "crypto"
    if _tokened(raw, s, where, _ENERGY):
        return "energy"
    if _tokened(raw, s, where, _SOFT):
        return "soft"
    # PREFIX-ONLY for bonds. A substring test made EUSTX50 -- the Euro Stoxx 50 INDEX -- a
    # bond, because "UST" sits inside "E-UST-X50" (2026-08-28). Ticker roots identify an
    # instrument at the START of the symbol; a loose contains-test silently reassigns whole
    # instruments to the wrong class, and every breadth count downstream inherits the error.
    # The boundary tests above extend that repair to the OTHER end of the root: `UST|05Y` is a
    # Treasury note and `UST|EC` is the Nasdaq index, and only the tail tells them apart.
    if _rooted(raw, s, where, _BOND):
        return "bond"
    if _tokened(raw, s, where, _INDEX):
        return "index"
    base, quote = s[:3], s[3:6]
    if len(s) >= 6 and base in _FX_MAJORS and quote in _FX_MAJORS:
        return "fx_major" if "USD" in (base, quote) else "fx_cross"
    if len(s) >= 6 and (base in _FX_MAJORS or quote in _FX_MAJORS):
        return "fx_exotic"
    if len(s) >= 6 and base in _FX_MINORS and quote in _FX_MINORS:
        return "fx_exotic"
    # Letters-then-digits with no FX reading is an index code (CA60, E35, NETH25 already caught
    # above; this keeps the NEXT broker index from silently reading unknown).
    if re.fullmatch(r"[A-Z]{1,6}\d{2,4}", s):
        return "index"
    # EQUITY CFDs arrive as COMPANY NAMES, not codes: mixed case ("Apple", "CocaCola" after
    # cleaning -- the raw string carries the lowercase), '&' or '-' in the raw, or a bare 1-5
    # character ticker (IBM, AMD, 3M) that nothing above claimed. The whole-broker expansion
    # (2026-08) brought ~70 of these and every one read "unknown", which kept an entire asset
    # class out of the breadth ledger while the law says hunt EVERYTHING the broker lists.
    if re.search(r"[a-z]", raw) or "&" in raw or "-" in raw:
        return "equity"
    if re.fullmatch(r"\d?[A-Z]{1,12}", s):
        return "equity"
    return "unknown"


@dataclass(frozen=True)
class Instrument:
    """One tradeable symbol with the cost model attached at discovery."""

    symbol: str
    asset_class: str
    bars: int
    contract_size: float
    tick_size: float
    tick_value: float
    min_volume: float
    volume_step: float
    median_spread_pts: float
    first: str = ""
    last: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def spread_cost_per_lot(self) -> float:
        """Spread per 1.0 lot IN ACCOUNT CURRENCY -- the figure a battery may charge.

        `median_spread_pts * tick_value`, NOT `* tick_size * contract_size`. The first version of
        this property used the latter and it is a units bug of exactly the kind that makes a
        universe ranking meaningless:

            EURUSD   12 pts -> 12.00 by size*contract, 10.37 via tick_value
            CADJPY   15 pts -> 1500.00 (!) by size*contract, 8.14 via tick_value

        `tick_size * contract_size` yields the spread in the QUOTE currency, so a JPY-quoted pair
        comes out in yen and reads ~150x more expensive than a dollar-quoted one. Ranking a mixed
        universe on that number would have excluded every JPY cross as unaffordable -- and the
        JPY crosses are where this desk's surviving edges actually live. `tick_value` is already
        denominated in the account currency, which is the only basis on which instruments can be
        compared to each other or charged against one book.
        """
        return float(self.median_spread_pts) * float(self.tick_value)

    @property
    def usable(self) -> bool:
        """Enough history AND a cost model that is actually populated.

        A symbol whose tick_size or contract_size is zero cannot be costed, and an uncosted
        instrument is far more dangerous than an absent one: it backtests as though trading were
        free and produces the best-looking cells in the sweep.
        """
        # ZERO SPREAD IS REAL ON THIS ACCOUNT (principal, 2026-08-29). Fusion ZERO is
        # commission-only: 24 of 251 symbols genuinely quote a 0.0 median spread and are charged
        # through commission instead. I briefly required a POSITIVE spread here, reasoning that no
        # broker quotes zero -- true of a spread account, false of this one, and it would have
        # excluded EURUSD, AUDUSD and USDJPY from the universe on a wrong premise.
        #
        # The instrument is still COSTED, which is what this property must actually guarantee:
        # `Costs.per_oz_roundtrip` charges spread PLUS `commission_per_lot * 2 * quote_per_account`,
        # so a zero-spread symbol pays two commissions per round trip -- measured, EURUSD costs
        # 17.21 per round trip, not nothing. The danger the docstring above warns about is an
        # instrument that cannot be charged AT ALL, and `tick_value > 0` is the guard that prevents
        # it: without a tick value the commission cannot be converted into price units.
        return (self.bars >= MIN_BARS and self.tick_size > 0
                and self.contract_size > 0 and self.median_spread_pts >= 0
                and self.tick_value > 0)


def classify_all(summary: dict[str, dict[str, Any]]) -> list[Instrument]:
    """Turn a `universe.json` payload into Instruments, preserving unusable ones as reported.

    Unusable symbols are RETURNED rather than dropped, so a caller can say how much of the
    offering was excluded and why. Silently shrinking the universe is how the energy complex went
    missing for the life of this desk.
    """
    out: list[Instrument] = []
    for sym, m in sorted(summary.items()):
        notes: list[str] = []
        bars = int(m.get("bars", 0) or 0)
        if bars < MIN_BARS:
            notes.append(f"insufficient history ({bars} bars < {MIN_BARS})")
        if not float(m.get("tick_size", 0) or 0) or not float(m.get("contract_size", 0) or 0):
            notes.append("no cost model (tick_size or contract_size is zero)")
        out.append(Instrument(
            symbol=sym, asset_class=asset_class(sym), bars=bars,
            contract_size=float(m.get("contract_size", 0) or 0),
            tick_size=float(m.get("tick_size", 0) or 0),
            tick_value=float(m.get("tick_value", 0) or 0),
            min_volume=float(m.get("min_volume", 0) or 0),
            volume_step=float(m.get("volume_step", 0) or 0),
            median_spread_pts=float(m.get("median_spread_pts", 0) or 0),
            first=str(m.get("first", "")), last=str(m.get("last", "")), notes=notes))
    return out


def coverage(instruments: list[Instrument]) -> dict[str, dict[str, int]]:
    """Per-class counts of what is usable versus merely present.

    The point of this report is the ZEROES. A class with no usable instruments has never been
    tested by this desk, and that absence is a research finding rather than a footnote -- it is
    how nine energy and index symbols stayed untested without anyone deciding they should be.
    """
    rep: dict[str, dict[str, int]] = {}
    for i in instruments:
        row = rep.setdefault(i.asset_class, {"usable": 0, "unusable": 0})
        row["usable" if i.usable else "unusable"] += 1
    return dict(sorted(rep.items()))
