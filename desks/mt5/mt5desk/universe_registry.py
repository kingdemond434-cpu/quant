"""THE ONE REGISTRY WRITER -- `data/universe/universe.json` had three of them and no schema.

WHAT WENT WRONG (measured 2026-08-26, this module is the repair).

Three separate producers wrote the same file, each with its own field set, each CLOBBERING the
others with `write_text(json.dumps(...))`:

    fetch_universe.py          23 syms   has tick_value    median_spread_pts = median of the H1
                                                           `spread` column (ALL hours)
    expand_universe.py        244 syms   no tick_value     median_spread_pts = symbol_info.spread
                                                           (a SNAPSHOT, under a median's name)
    scripts/download_all_*    197 syms   no tick_value     median_spread_pts = symbol_info.spread

The file's history alternates between them hour to hour. Three consequences, all live:

  1. `tick_value` WAS DELETED FROM ALL 197 SYMBOLS. It is the only field that carries a price in
     ACCOUNT currency, so `Instrument.spread_cost_per_lot` -- whose docstring exists purely to
     warn that `median_spread_pts * tick_size * contract_size` reads a JPY cross ~150x too
     expensive -- returned 0.0 for every symbol on the desk. `classify_all` over the live file
     returned 0 usable instruments out of 197. Absence read as a clean verdict (WS-005).

  2. `median_spread_pts` FLIPPED SCALE. EURUSD reads 12 under one producer and 0 under the next.
     Through the wrong (quote-currency) formula that is a modelled spread of $12/lot vs the
     $0.05 floor; for CADJPY it is 1500 vs 0.05. The same candidate is uneconomic or free
     depending on which producer last ran.

  3. THE COST HASH IS PART OF SLEEVE IDENTITY, so every flip breaks live forward clocks
     TERMINALLY. Eleven were IDENTITY_BROKEN on `cost_hash` when this was found, which is the
     desk's readiness blocker: a 14-day window cannot complete if the cost model changes
     under it every few hours. The identity law is right and is NOT loosened here -- the input
     it verifies is what had to stop moving for no reason.

WHAT THIS MODULE ENFORCES

  * MERGE, NEVER CLOBBER. A producer that does not know a field must not be able to delete it.
    `merge()` unions symbols and preserves any field the incoming payload omits, recording which
    source last supplied each field.
  * A DEGENERATE READING IS NOT A MEASUREMENT. `symbol_info.spread` returns 0 for a symbol with
    no fresh tick, and `bars: 0` next to a 50,000-row parquet is a stub. Neither is allowed to
    overwrite a real prior value; both are recorded as UNMEASURED so a consumer can refuse
    rather than silently cost the trade at a floor.
  * COST IS QUOTED IN THE ACCOUNT'S CURRENCY OR IT IS NOT A COST. `tick_value` is derivable from
    the desk's own bars and is derived here rather than left absent.

THE ACCOUNT CURRENCY IS EUR, AND IT WAS MEASURED, NOT ASSUMED. Deriving tick_value as
`tick_size * contract_size * (quote -> USD)` reproduces every one of the 23 tick_values the
broker itself reported, uniformly 15.8-16.9% high. That single factor is 1.1585 = EURUSD, and
dividing by it lands every symbol within 1% of the broker's own number (XAGUSD 4.3159 vs 4.3161,
CAD 0.6227 vs 0.6224, JPY 0.5428 vs 0.5418 -- the residual is rate drift since the broker read).
A uniform factor across metals, JPY crosses, CHF and CAD is not a coincidence a fudge could
produce; it is the account denomination.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

#: The account's denomination, derived from the broker's own tick_value table (see module
#: docstring). Every cost this desk charges is in this currency; a number in quote currency is
#: not comparable across a mixed universe and must never be charged against one book.
ACCOUNT_CCY = "EUR"

#: Fields a consumer is entitled to assume exist. Losing one is a silent capability deletion,
#: which is why `defects()` reports a missing field rather than letting a reader see a default.
REQUIRED_FIELDS = ("tick_size", "contract_size", "tick_value", "median_spread_pts", "bars")

#: Fields whose zero is a STUB rather than a measurement. `symbol_info.spread` is 0 when no tick
#: has arrived; `bars` is 0 when a writer never counted them. A real broker spread CAN be 0 on a
#: raw account -- so a zero is not rewritten to something invented, it is marked unmeasured and
#: left for the cost resolver to fall back on realised fills.
ZERO_IS_A_STUB = ("tick_size", "contract_size", "tick_value", "bars")

#: ISO-4217 codes this broker quotes in. A SEED for reading a denomination off a symbol name,
#: never a limit on the universe (LAWS anti-hardcode): a code absent here yields None, which
#: makes the symbol UNCOSTED and visible in `defects()` rather than silently mispriced. Extend it
#: when the broker adds a quote currency -- the fence will name the symbol that needs it.
QUOTE_CCY_SEED = frozenset({
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK", "DKK",
    "PLN", "CZK", "HUF", "TRY", "ZAR", "MXN", "SGD", "HKD", "CNH", "THB", "ILS",
    # Added 2026-08-26 because the fence named the six exotics it could not cost. That is the
    # seed working as designed: the gap announced itself instead of being priced by assumption.
    "RUB", "BRL", "IDR", "INR", "KRW",
})

#: The field MetaTrader5 itself uses for the currency a symbol's profit is denominated in. When a
#: producer captures it, NOTHING has to be inferred from the symbol name -- which is the only way
#: to cost a share or index CFD, whose name carries no denomination at all. None of the three
#: producers records it today; `check_universe_registry` reports every symbol that needs it.
VENUE_CCY_FIELD = "currency_profit"

_ALNUM = re.compile(r"[^A-Z0-9]")


def quote_currency(symbol: str, row: dict[str, Any] | None = None) -> str | None:
    """The currency a symbol's PRICE is expressed in, or None when it cannot be established.

    THE VENUE'S OWN ANSWER WINS. If `row` carries `currency_profit`, that is MetaTrader5's own
    field and no inference happens -- which is the only correct route for a share or index CFD,
    whose name ("3M", "AUS200") carries no denomination to read.

    Otherwise the name is parsed against a seed of known codes, and an unknown one returns None
    rather than guessing USD. A three-letter SHAPE is not a currency: `AAPL` ends in "APL" and a
    shape test reads it as one, then prices a share CFD off a currency that does not exist. An
    assumed denomination is exactly the error this module exists to stop, and a caller that gets
    None records UNMEASURED instead of charging a made-up cost.
    """
    venue = (row or {}).get(VENUE_CCY_FIELD)
    if isinstance(venue, str) and len(venue.strip()) == 3:
        return venue.strip().upper()
    s = _ALNUM.sub("", str(symbol).upper())
    if len(s) == 6 and s[:3] in QUOTE_CCY_SEED and s[3:] in QUOTE_CCY_SEED:
        return s[3:]
    # Metals, crypto and index CFDs are near-universally quoted against a currency named in the
    # suffix (XAUUSD, BTCUSD, XAGEUR). A longer symbol ending in a known code is that shape.
    if len(s) > 3 and s[-3:] in QUOTE_CCY_SEED:
        return s[-3:]
    return None


def _rate_to_account(quote: str, closes: dict[str, float]) -> float | None:
    """`quote` units -> ACCOUNT_CCY, from the desk's own last bars. None when unbridgeable.

    Tries the direct pair both ways, then triangulates through USD, which is the only leg the
    desk is guaranteed to hold for every quote currency it trades.
    """
    quote = quote.upper()
    if quote == ACCOUNT_CCY:
        return 1.0

    def close(sym: str) -> float | None:
        v = closes.get(sym)
        return float(v) if v is not None and float(v) != 0.0 else None

    direct = close(f"{ACCOUNT_CCY}{quote}")          # quote per 1 account unit
    if direct:
        return 1.0 / direct
    inverse = close(f"{quote}{ACCOUNT_CCY}")         # account per 1 quote unit
    if inverse:
        return inverse

    # Triangulate: (quote -> USD) x (USD -> account).
    if quote == "USD":
        quote_usd: float | None = 1.0
    else:
        usd_quote = close(f"USD{quote}")             # quote per 1 USD
        quote_usd = (1.0 / usd_quote) if usd_quote else close(f"{quote}USD")
    if not quote_usd:
        return None
    acct_usd = close(f"{ACCOUNT_CCY}USD")            # USD per 1 account unit
    if not acct_usd:
        return None
    return quote_usd / acct_usd


def derive_tick_value(symbol: str, tick_size: Any, contract_size: Any,
                      closes: dict[str, float], row: dict[str, Any] | None = None
                      ) -> float | None:
    """Value of one tick of `symbol` for 1.0 lot, IN ACCOUNT CURRENCY. None when underivable.

    This is the field three producers dropped. It is not a convenience: it is the only basis on
    which a JPY cross and a gold CFD can be charged against the same book, and without it every
    cost model on the desk reads zero.
    """
    try:
        ts, cs = float(tick_size), float(contract_size)
    except (TypeError, ValueError):
        return None
    if ts <= 0 or cs <= 0:
        return None
    quote = quote_currency(symbol, row)
    if quote is None:
        return None
    rate = _rate_to_account(quote, closes)
    if rate is None:
        return None
    return ts * cs * rate


def spread_cost_per_lot(row: dict[str, Any]) -> float | None:
    """Spread for 1.0 lot in ACCOUNT currency, or None when the row cannot be costed.

    `median_spread_pts * tick_value`. NEVER `* tick_size * contract_size` -- that is the quote
    currency and reads a JPY cross ~150x too expensive, which deletes the JPY crosses (where this
    desk's surviving edges actually live) from every ranking that uses it.

    None is deliberate and is not interchangeable with 0.0. An uncosted instrument backtests as
    though trading were free and produces the best-looking cells in the sweep, so a caller must
    handle the absence explicitly rather than receive a number that flatters it.
    """
    tv, pts = row.get("tick_value"), row.get("median_spread_pts")
    if tv is None or pts is None:
        return None
    try:
        tv_f, pts_f = float(tv), float(pts)
    except (TypeError, ValueError):
        return None
    return None if tv_f == 0.0 else pts_f * tv_f


def _degenerate(field: str, value: Any) -> bool:
    """True when `value` is a stub for `field` rather than a measurement."""
    if value is None:
        return True
    if field in ZERO_IS_A_STUB:
        try:
            return float(value) <= 0
        except (TypeError, ValueError):
            return True
    return False


def merge(base: dict[str, Any], incoming: dict[str, Any], *, source: str,
          now: str | None = None) -> dict[str, Any]:
    """Union `incoming` into `base` without letting a partial producer delete anything.

    A field present and non-degenerate in `incoming` wins. A field the producer does not know
    -- or knows only as a stub -- leaves the existing value untouched and is recorded, so
    `bars: 0` from a writer that never counted them can never overwrite 50,000 real bars.
    """
    stamp = now or datetime.now(UTC).isoformat(timespec="seconds")
    out: dict[str, Any] = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for sym, row in incoming.items():
        if not isinstance(row, dict):
            continue
        prev = out.get(sym)
        prev = dict(prev) if isinstance(prev, dict) else {}
        prov = dict(prev.get("_provenance") or {})
        for field, value in row.items():
            if field == "_provenance":
                continue
            if _degenerate(field, value) and field in prev and not _degenerate(field, prev[field]):
                prov.setdefault(field, {})
                continue
            prev[field] = value
            prov[field] = {"source": source, "at": stamp}
        prev["_provenance"] = prov
        out[sym] = prev
    return out


def backfill_tick_values(registry: dict[str, Any], closes: dict[str, float], *,
                         source: str = "derived", now: str | None = None) -> tuple[int, list[str]]:
    """Fill a usable `tick_value` wherever one is missing. Returns (filled, still_underivable)."""
    stamp = now or datetime.now(UTC).isoformat(timespec="seconds")
    filled, missing = 0, []
    for sym, row in registry.items():
        if not isinstance(row, dict):
            continue
        if not _degenerate("tick_value", row.get("tick_value")):
            continue
        tv = derive_tick_value(sym, row.get("tick_size"), row.get("contract_size"), closes, row)
        if tv is None:
            missing.append(sym)
            continue
        row["tick_value"] = tv
        prov = dict(row.get("_provenance") or {})
        prov["tick_value"] = {"source": source, "at": stamp, "account_ccy": ACCOUNT_CCY}
        row["_provenance"] = prov
        filled += 1
    return filled, missing


def defects(registry: dict[str, Any], *, parquet_bars: dict[str, int] | None = None,
            realized_spread_pts: dict[str, float] | None = None) -> list[str]:
    """Every way this registry would silently mislead a consumer. Empty list means intact.

    Ordered by what each one costs: a missing cost field zeroes a cost model everywhere; a
    stubbed bar count empties a universe; a zero spread contradicted by the desk's OWN fills is a
    measurement that reality has already refuted.
    """
    parquet_bars = parquet_bars or {}
    realized_spread_pts = realized_spread_pts or {}
    out: list[str] = []
    rows = {s: r for s, r in registry.items() if isinstance(r, dict)}
    if not rows:
        return ["registry is empty -- 0 symbols, which no consumer can distinguish from a "
                "universe with nothing worth trading"]
    for field in REQUIRED_FIELDS:
        absent = sorted(s for s, r in rows.items() if _degenerate(field, r.get(field)))
        if absent:
            out.append(f"{field}: missing or stubbed on {len(absent)}/{len(rows)} symbol(s) "
                       f"(e.g. {', '.join(absent[:5])})")
    stubbed = sorted(s for s, r in rows.items()
                     if _degenerate("bars", r.get("bars")) and parquet_bars.get(s, 0) > 0)
    if stubbed:
        out.append(f"bars: {len(stubbed)} symbol(s) report 0 bars while a parquet with real rows "
                   f"sits on disk (e.g. {', '.join(stubbed[:5])})")
    refuted = sorted(s for s, r in rows.items()
                     if float(r.get("median_spread_pts") or 0) <= 0
                     and realized_spread_pts.get(s, 0) > 0)
    if refuted:
        out.append(f"median_spread_pts: {len(refuted)} symbol(s) read 0 while this desk's OWN "
                   f"fills measured a positive spread (e.g. {', '.join(refuted[:5])})")
    uncosted = sorted(s for s, r in rows.items() if spread_cost_per_lot(r) is None)
    if uncosted:
        out.append(f"cost: {len(uncosted)}/{len(rows)} symbol(s) cannot be costed in "
                   f"{ACCOUNT_CCY} at all (e.g. {', '.join(uncosted[:5])})")
    return out
