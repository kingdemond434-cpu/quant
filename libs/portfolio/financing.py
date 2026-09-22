"""THE COLLATERAL / SETTLEMENT / BALANCE-SHEET LAYER of a CFD book (LAWS 5m), pure and typed.

WHAT THIS IS. The account's balance sheet as the allocator needs to read it: the cash ladder
(balance, equity, margin used, free margin, margin level), the margin each instrument requires
under the broker's own conventions, the swap/financing curve per instrument and side, the
settlement calendar (broker daily close, the triple-swap weekday, the weekend close), the
currency funding of an account whose positions settle in other currencies, intraday liquidity,
the distance to a margin call, and a forced-deleveraging simulation under named stress scenarios.

EVERYTHING HERE IS EVIDENCE AND NOTHING HERE IS A RAIL. No function in this module returns a
fraction, a cap or a veto; each returns a measurement with a status, and the allocator reads
the measurement through its own E[log W] arithmetic (GROWTH_GOVERNANCE Rule 1 and Rule 2). A
number the desk cannot measure is `UNMEASURED` -- a value with a reason -- never a zero and
never a default that happens to look safe (LAWS L1.28a).

BORROW IS UNMEASURED BY CONSTRUCTION. A CFD account has no securities-lending leg: there is no
stock borrow to locate, no rebate, no recall risk, and the cost of a short is entirely inside
`swap_short`. `borrow()` therefore returns that fact as a status rather than inventing a cost
the venue never charges; an invented borrow rate would be a deduction with no measurement behind
it, which is exactly the kind of quiet shrinkage the growth governance forbids.

THE MT5 CONVENTIONS, so they are not re-derived per caller (a sign convention re-derived at each
call site is a sign error waiting for its first consumer):

  * `swap_long` / `swap_short` are POSITIVE WHEN THE VENUE PAYS THE DESK (MT5's own sign).
  * `swap_mode` 1 (POINTS): money per lot per night = points x tick_value x (point / tick_size).
    `swap_mode` 5/6 (INTEREST): an annual PERCENT of the notional, on a 360-day bank year.
    Mode 0 is disabled (0.0). Any other mode is UNMEASURED: this desk has not established its
    unit and will not guess one.
  * `swap_rollover3days` is MT5's `ENUM_DAY_OF_WEEK` (0 = Sunday .. 6 = Saturday) of the night
    the venue charges three nights at once -- Wednesday (3) on forex and metals, Friday (5) on
    share and index CFDs on this venue's tape.
  * `margin_initial == 0.0` means "use the contract size": margin per lot is the notional over
    the leverage tier. A non-zero `margin_initial` is a fixed initial margin per lot in the
    margin currency.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
DECLARED = "DECLARED"

SWAP_MODE_DISABLED = 0
SWAP_MODE_POINTS = 1
SWAP_MODE_INTEREST_CURRENT = 5
SWAP_MODE_INTEREST_OPEN = 6
#: The bank year the venue's percent swaps are quoted on. A DECLARED broker convention.
DAY_COUNT = 360.0
#: MT5 ENUM_DAY_OF_WEEK (0 = Sunday) -> Python weekday (0 = Monday).
MT5_WEEKDAY_TO_PY: dict[int, int] = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
#: The margin-call line every MT5 venue draws at 100% margin level; the STOP-OUT level below it
#: is the venue's own number (`account_info().margin_so_so`) and is UNMEASURED until read.
MARGIN_CALL_LEVEL_PCT = 100.0
#: Currencies this module will treat as a funding leg. Anything else in a symbol is an
#: instrument (an index, a metal, a share), not a currency the account funds.
CURRENCIES: frozenset[str] = frozenset({
    "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK", "DKK", "PLN", "HUF",
    "CZK", "ZAR", "MXN", "SGD", "HKD", "TRY", "CNH", "CNY", "ILS", "THB", "RUB", "INR", "KRW",
})


# ------------------------------------------------------------------------------ measurements


@dataclass(frozen=True)
class Measure:
    """A number with the status that says whether it was measured, declared or is unknown."""

    value: float | None
    status: str
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        v = self.value
        return {"value": (None if v is None or not math.isfinite(v) else round(v, 8)),
                "status": self.status, "why": self.why}

    @property
    def known(self) -> bool:
        return self.value is not None and math.isfinite(self.value)


def measured(value: float, why: str = "") -> Measure:
    return Measure(float(value), MEASURED, why)


def declared(value: float, why: str) -> Measure:
    return Measure(float(value), DECLARED, why)


def unmeasured(why: str) -> Measure:
    return Measure(None, UNMEASURED, why)


def _f(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _i(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------- instruments


@dataclass(frozen=True)
class InstrumentTerms:
    """One instrument's contract terms as the broker registry publishes them."""

    symbol: str
    asset_class: str = ""
    contract_size: float | None = None
    tick_size: float | None = None
    #: account currency per tick per lot, as the venue reports it
    tick_value: float | None = None
    point: float | None = None
    currency_margin: str = ""
    currency_profit: str = ""
    swap_long: float | None = None
    swap_short: float | None = None
    swap_mode: int | None = None
    swap_rollover3days: int | None = None
    margin_initial: float | None = None
    margin_maintenance: float | None = None
    #: the leverage tier that applies to this instrument; None is UNMEASURED
    leverage: float | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any], *, leverage: float | None = None,
                 symbol: str | None = None) -> InstrumentTerms:
        """From a `contract_terms` tape row or a `universe.json` registry row."""
        digits = _i(row.get("digits"))
        point = _f(row.get("point"))
        if point is None and digits is not None and 0 <= digits <= 12:
            point = 10.0 ** (-digits)
        return cls(
            symbol=str(symbol or row.get("symbol") or ""),
            asset_class=str(row.get("asset_class") or row.get("category") or ""),
            contract_size=_f(row.get("contract_size")),
            tick_size=_f(row.get("tick_size")),
            tick_value=_f(row.get("tick_value")),
            point=point,
            currency_margin=str(row.get("currency_margin") or ""),
            currency_profit=str(row.get("currency_profit") or ""),
            swap_long=_f(row.get("swap_long")),
            swap_short=_f(row.get("swap_short")),
            swap_mode=_i(row.get("swap_mode")),
            swap_rollover3days=_i(row.get("swap_rollover3days")),
            margin_initial=_f(row.get("margin_initial")),
            margin_maintenance=_f(row.get("margin_maintenance")),
            leverage=_f(row.get("leverage")) if leverage is None else _f(leverage),
        )

    def legs(self) -> tuple[str, str]:
        """(base, quote). A pair of two DIFFERENT currencies is a currency pair; anything else
        -- an index, a metal, a share, whose margin and profit currency coincide -- is the
        instrument itself against its profit currency."""
        cm, cp = self.currency_margin.upper(), self.currency_profit.upper()
        if cm in CURRENCIES and cp in CURRENCIES and cm != cp:
            return cm, cp
        core = self.symbol.upper()
        if len(core) == 6 and core[:3] in CURRENCIES and core[3:] in CURRENCIES \
                and core[:3] != core[3:]:
            return core[:3], core[3:]
        quote = cp or (core[3:6] if len(core) == 6 and core[3:6] in CURRENCIES else "")
        return self.symbol, quote


def convert(currency: str, account_ccy: str, rates: Mapping[str, float]) -> Measure:
    """Units of account currency per unit of `currency`, from a `{"EURUSD": 1.08, ...}` table.

    An absent rate is UNMEASURED (L1.28a): never 1.0 and never the last rate that worked.
    """
    c, a = currency.upper(), account_ccy.upper()
    if not c:
        return unmeasured("no currency to convert")
    if c == a:
        return measured(1.0, "same currency")
    direct = _f(rates.get(f"{c}{a}"))
    if direct is not None and direct > 0:
        return measured(direct, f"{c}{a} rate")
    inverse = _f(rates.get(f"{a}{c}"))
    if inverse is not None and inverse > 0:
        return measured(1.0 / inverse, f"1/{a}{c} rate")
    return unmeasured(f"no {c}{a} or {a}{c} rate supplied")


def swap_per_lot_night(terms: InstrumentTerms, side: str, price: float | None = None
                       ) -> Measure:
    """Money per lot per night in ACCOUNT currency, MT5 sign: POSITIVE is a credit to the desk."""
    s = side.upper()
    if s not in ("LONG", "SHORT", "BUY", "SELL"):
        return unmeasured(f"side {side!r} is neither LONG nor SHORT")
    pts = terms.swap_long if s in ("LONG", "BUY") else terms.swap_short
    if pts is None:
        return unmeasured(f"{terms.symbol}: no swap rate for {s} in the registry")
    mode = terms.swap_mode
    if mode is None:
        return unmeasured(f"{terms.symbol}: no swap_mode, the unit of {pts} is unknown")
    if mode == SWAP_MODE_DISABLED:
        return measured(0.0, "swap disabled by the venue (mode 0)")
    tv, ts = terms.tick_value, terms.tick_size
    if mode == SWAP_MODE_POINTS:
        if tv is None or tv <= 0 or ts is None or ts <= 0:
            return unmeasured(f"{terms.symbol}: mode 1 needs tick_value and tick_size")
        point = terms.point if terms.point and terms.point > 0 else ts
        return measured(float(pts) * tv * (point / ts),
                        "mode 1 (POINTS): points x tick_value x point/tick_size")
    if mode in (SWAP_MODE_INTEREST_CURRENT, SWAP_MODE_INTEREST_OPEN):
        if price is None or price <= 0:
            return unmeasured(f"{terms.symbol}: mode {mode} is an annual percent of notional "
                              "and needs a price")
        if tv is None or tv <= 0 or ts is None or ts <= 0:
            return unmeasured(f"{terms.symbol}: mode {mode} needs tick_value/tick_size")
        notional_acct = price * (tv / ts)
        return measured(float(pts) / 100.0 * notional_acct / DAY_COUNT,
                        f"mode {mode} (INTEREST): pct/100 x price x tick_value/tick_size / "
                        f"{DAY_COUNT:.0f} (declared bank year)")
    return unmeasured(f"{terms.symbol}: swap_mode {mode} has no established unit on this desk")


def swap_curve(terms: InstrumentTerms, price: float | None = None) -> dict[str, Any]:
    """Both sides of one instrument's financing, per lot per night and annualised on notional."""
    out: dict[str, Any] = {"symbol": terms.symbol}
    notional = notional_per_lot_profit_ccy(terms, price)
    for side in ("LONG", "SHORT"):
        m = swap_per_lot_night(terms, side, price)
        row = m.as_dict()
        if m.known and notional.known and notional.value and m.value is not None:
            row["annual_pct_of_notional"] = round(m.value * 365.0 / notional.value * 100.0, 4)
        out[side] = row
    out["triple_swap_weekday"] = triple_swap_weekday(terms)
    return out


def notional_per_lot_profit_ccy(terms: InstrumentTerms, price: float | None) -> Measure:
    """One lot's notional in the PROFIT currency: contract_size x price."""
    if terms.contract_size is None or terms.contract_size <= 0:
        return unmeasured(f"{terms.symbol}: no contract size")
    if price is None or price <= 0:
        return unmeasured(f"{terms.symbol}: no price")
    return measured(terms.contract_size * price, "contract_size x price")


def margin_required(terms: InstrumentTerms, lots: float, price: float | None,
                    rates: Mapping[str, float], account_ccy: str) -> Measure:
    """Initial margin for `lots` in ACCOUNT currency under the venue's own convention."""
    if lots == 0:
        return measured(0.0, "no position")
    mi = terms.margin_initial
    if mi is not None and mi > 0 and terms.contract_size is not None \
            and abs(mi - terms.contract_size) > 1e-9:
        conv = convert(terms.currency_margin, account_ccy, rates)
        if not conv.known or conv.value is None:
            return unmeasured(f"{terms.symbol}: fixed initial margin in {terms.currency_margin} "
                              f"but {conv.why}")
        return measured(abs(lots) * mi * conv.value, "fixed margin_initial per lot x rate")
    if terms.leverage is None or terms.leverage <= 0:
        return unmeasured(f"{terms.symbol}: leverage tier UNMEASURED")
    notional = notional_per_lot_profit_ccy(terms, price)
    if not notional.known or notional.value is None:
        return unmeasured(f"{terms.symbol}: {notional.why}")
    conv = convert(terms.currency_profit, account_ccy, rates)
    if not conv.known or conv.value is None:
        return unmeasured(f"{terms.symbol}: {conv.why}")
    return measured(abs(lots) * notional.value * conv.value / terms.leverage,
                    "lots x contract_size x price / leverage, in account currency")


# ------------------------------------------------------------------------------- settlement


def triple_swap_weekday(terms: InstrumentTerms) -> int | None:
    """Python weekday (0 = Monday) of the triple-swap night, or None when the registry is silent."""
    d = terms.swap_rollover3days
    return None if d is None else MT5_WEEKDAY_TO_PY.get(int(d))


def rollover_nights(entry: datetime, exit_at: datetime, *, rollover_hour_utc: int,
                    triple_weekday: int | None) -> int:
    """Nights CHARGED between entry and exit: one per weekday rollover, three on the triple night.

    The venue rolls at its daily close (`rollover_hour_utc`), Monday to Friday; the weekend
    carries no rollover of its own -- its two nights are what the triple charge pays for.
    """
    if exit_at <= entry:
        return 0
    first = entry.astimezone(UTC).replace(hour=rollover_hour_utc, minute=0, second=0,
                                          microsecond=0)
    if first <= entry.astimezone(UTC):
        first += timedelta(days=1)
    nights = 0
    t = first
    end = exit_at.astimezone(UTC)
    while t <= end:
        wd = t.weekday()
        if wd < 5:
            nights += 3 if triple_weekday is not None and wd == triple_weekday else 1
        t += timedelta(days=1)
    return nights


def settlement_calendar(now: datetime, terms: InstrumentTerms, *, rollover_hour_utc: int,
                        weekend_close_hour_utc: int | None = None) -> dict[str, Any]:
    """The next rollover, whether it is the triple night, and the next weekend close."""
    t = now.astimezone(UTC)
    nxt = t.replace(hour=rollover_hour_utc, minute=0, second=0, microsecond=0)
    if nxt <= t:
        nxt += timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    triple = triple_swap_weekday(terms)
    close_h = rollover_hour_utc if weekend_close_hour_utc is None else weekend_close_hour_utc
    fri = t.replace(hour=close_h, minute=0, second=0, microsecond=0)
    while fri.weekday() != 4 or fri <= t:
        fri += timedelta(days=1)
    return {"next_rollover_utc": nxt.isoformat(),
            "hours_to_next_rollover": round((nxt - t).total_seconds() / 3600.0, 3),
            "nights_charged_at_next": 3 if triple is not None and nxt.weekday() == triple else 1,
            "triple_swap_weekday": triple,
            "weekend_close_utc": fri.isoformat(),
            "rollover_hour_utc": rollover_hour_utc}


# --------------------------------------------------------------------------- balance sheet


@dataclass(frozen=True)
class OpenPosition:
    symbol: str
    #: "LONG" or "SHORT"
    side: str
    lots: float
    price_open: float
    price: float | None = None
    #: floating P&L in ACCOUNT currency, as the terminal reports it
    floating_pnl: float | None = None
    #: swap accrued so far in ACCOUNT currency (MT5 sign: positive is a credit)
    swap_accrued: float | None = None
    sleeve: str = ""

    @property
    def sign(self) -> float:
        return 1.0 if self.side.upper() in ("LONG", "BUY") else -1.0

    @property
    def mark(self) -> float:
        return self.price if self.price is not None and self.price > 0 else self.price_open


@dataclass(frozen=True)
class BalanceSheet:
    account_ccy: str
    balance: float
    equity: float
    margin_used: Measure
    #: the venue's stop-out level in percent of margin level; UNMEASURED until read
    stop_out_level_pct: Measure = field(default_factory=lambda: unmeasured("not read"))
    source: str = ""

    @property
    def floating_pnl(self) -> float:
        return self.equity - self.balance

    @property
    def free_margin(self) -> Measure:
        if not self.margin_used.known or self.margin_used.value is None:
            return unmeasured(self.margin_used.why)
        return measured(self.equity - self.margin_used.value, "equity - margin used")

    @property
    def margin_level_pct(self) -> Measure:
        m = self.margin_used
        if not m.known or m.value is None:
            return unmeasured(m.why)
        if m.value <= 0:
            return measured(math.inf, "no margin in use")
        return measured(self.equity / m.value * 100.0, "equity / margin x 100")

    def as_dict(self) -> dict[str, Any]:
        lvl = self.margin_level_pct
        return {"account_ccy": self.account_ccy, "balance": round(self.balance, 2),
                "equity": round(self.equity, 2), "floating_pnl": round(self.floating_pnl, 2),
                "margin_used": self.margin_used.as_dict(),
                "free_margin": self.free_margin.as_dict(),
                "margin_level_pct": ({"value": None if lvl.value is None or
                                      not math.isfinite(lvl.value) else round(lvl.value, 2),
                                      "status": lvl.status, "why": lvl.why}),
                "stop_out_level_pct": self.stop_out_level_pct.as_dict(),
                "source": self.source}


def notional_account_ccy(pos: OpenPosition, terms: InstrumentTerms,
                         rates: Mapping[str, float], account_ccy: str) -> Measure:
    """SIGNED notional of one position in account currency (positive when long)."""
    n = notional_per_lot_profit_ccy(terms, pos.mark)
    if not n.known or n.value is None:
        return unmeasured(n.why)
    conv = convert(terms.currency_profit, account_ccy, rates)
    if not conv.known or conv.value is None:
        return unmeasured(f"{pos.symbol}: {conv.why}")
    return measured(pos.sign * abs(pos.lots) * n.value * conv.value,
                    "sign x lots x contract_size x price x rate")


def cash_ladder(sheet: BalanceSheet, positions: Sequence[OpenPosition],
                terms_by_symbol: Mapping[str, InstrumentTerms], rates: Mapping[str, float],
                *, next_rollover_nights: int = 1) -> dict[str, Any]:
    """The ladder: what is cash, what is pledged, what the next settlement takes, what is free."""
    gross = 0.0
    n_unmeasured_notional = 0
    next_swap = 0.0
    n_unmeasured_swap = 0
    margin_sum = 0.0
    n_unmeasured_margin = 0
    for p in positions:
        t = terms_by_symbol.get(p.symbol)
        if t is None:
            n_unmeasured_notional += 1
            n_unmeasured_swap += 1
            n_unmeasured_margin += 1
            continue
        nt = notional_account_ccy(p, t, rates, sheet.account_ccy)
        if nt.known and nt.value is not None:
            gross += abs(nt.value)
        else:
            n_unmeasured_notional += 1
        sw = swap_per_lot_night(t, p.side, p.mark)
        if sw.known and sw.value is not None:
            next_swap += sw.value * abs(p.lots) * next_rollover_nights
        else:
            n_unmeasured_swap += 1
        mg = margin_required(t, p.lots, p.mark, rates, sheet.account_ccy)
        if mg.known and mg.value is not None:
            margin_sum += mg.value
        else:
            n_unmeasured_margin += 1
    free = sheet.free_margin
    return {
        "balance": round(sheet.balance, 2), "equity": round(sheet.equity, 2),
        "margin_used": sheet.margin_used.as_dict(),
        "margin_rebuilt_from_terms": ({"value": round(margin_sum, 2), "status": MEASURED,
                                       "why": "sum of margin_required over positions"}
                                      if positions and n_unmeasured_margin == 0 else
                                      unmeasured(f"{n_unmeasured_margin} position(s) without a "
                                                 "leverage tier or price").as_dict()),
        "free_margin": free.as_dict(),
        "gross_notional": ({"value": round(gross, 2), "status": MEASURED, "why": "sum |notional|"}
                           if n_unmeasured_notional == 0 else
                           unmeasured(f"{n_unmeasured_notional} position(s) unpriced").as_dict()),
        "gross_leverage": (round(gross / sheet.equity, 4)
                           if sheet.equity > 0 and n_unmeasured_notional == 0 else None),
        "next_settlement_swap": ({"value": round(next_swap, 4), "status": MEASURED,
                                  "why": f"{next_rollover_nights} night(s) at the next rollover, "
                                         "MT5 sign (positive is a credit)"}
                                 if n_unmeasured_swap == 0 else
                                 unmeasured(f"{n_unmeasured_swap} position(s) without a "
                                            "priced swap").as_dict()),
        "intraday_liquidity": {
            "free_margin_share_of_equity": (round(free.value / sheet.equity, 4)
                                            if free.known and free.value is not None
                                            and sheet.equity > 0 else None),
            "status": free.status,
        },
        "n_positions": len(positions),
    }


def funding_by_currency(positions: Sequence[OpenPosition],
                        terms_by_symbol: Mapping[str, InstrumentTerms],
                        rates: Mapping[str, float], account_ccy: str,
                        funding_pairs: Mapping[str, InstrumentTerms] | None = None,
                        prices: Mapping[str, float] | None = None) -> dict[str, Any]:
    """What the account funds in each foreign currency, and what that funding is priced at.

    A EUR account long EURUSD is long EUR and short USD: it has borrowed USD, and the venue
    prices that borrowing in the EURUSD swap. So for every currency the book expresses, the
    signed notional is summed by leg, and the price of funding that leg for THIS account is read
    off the account-currency pair's own swap (`EURUSD` for USD funding of a EUR account), per
    lot per night and annualised on the notional: MEASURED when that pair is in `funding_pairs`,
    UNMEASURED otherwise -- never a rate borrowed from a different pair.
    """
    a = account_ccy.upper()
    legs: dict[str, float] = {}
    swap_by_ccy: dict[str, float] = {}
    n_unpriced = 0
    for p in positions:
        t = terms_by_symbol.get(p.symbol)
        if t is None:
            n_unpriced += 1
            continue
        nt = notional_account_ccy(p, t, rates, a)
        if not nt.known or nt.value is None:
            n_unpriced += 1
            continue
        base, quote = t.legs()
        legs[base] = legs.get(base, 0.0) + nt.value
        if quote:
            legs[quote] = legs.get(quote, 0.0) - nt.value
        sw = swap_per_lot_night(t, p.side, p.mark)
        if sw.known and sw.value is not None and quote:
            swap_by_ccy[quote] = swap_by_ccy.get(quote, 0.0) + sw.value * abs(p.lots)
    out: dict[str, Any] = {}
    fp = funding_pairs or {}
    px = prices or {}
    for ccy, notional in sorted(legs.items()):
        row: dict[str, Any] = {"net_notional_account_ccy": round(notional, 2),
                               "is_currency": ccy in CURRENCIES,
                               "swap_on_positions_per_night": round(swap_by_ccy.get(ccy, 0.0), 4)}
        if ccy == a or ccy not in CURRENCIES:
            row["funding_price"] = (measured(0.0, "the account currency funds itself").as_dict()
                                    if ccy == a else
                                    unmeasured("not a currency leg: an instrument, not funding")
                                    .as_dict())
        else:
            pair = fp.get(f"{a}{ccy}") or fp.get(f"{ccy}{a}")
            if pair is None:
                row["funding_price"] = unmeasured(f"no {a}{ccy} contract terms supplied").as_dict()
            else:
                # The account is SHORT the foreign currency when its net leg is negative, which
                # is what a long in the account-currency pair does (long EURUSD = short USD).
                short_foreign = notional < 0
                pair_is_direct = pair.symbol.upper().startswith(a)
                side = ("LONG" if short_foreign else "SHORT") if pair_is_direct \
                    else ("SHORT" if short_foreign else "LONG")
                price = _f(px.get(pair.symbol)) or _f(rates.get(pair.symbol))
                sw = swap_per_lot_night(pair, side, price)
                lot_notional = notional_per_lot_profit_ccy(pair, price)
                conv = convert(pair.currency_profit, a, rates)
                if (sw.known and sw.value is not None and lot_notional.known
                        and lot_notional.value and conv.known and conv.value):
                    per_lot_acct = lot_notional.value * conv.value
                    annual_bp = sw.value * 365.0 / per_lot_acct * 1e4
                    row["funding_price"] = {
                        "value": round(annual_bp, 3), "status": MEASURED,
                        "why": (f"{pair.symbol} {side} swap {sw.value:.4f}/lot/night on "
                                f"{per_lot_acct:.0f} {a} notional, annualised bp (MT5 sign: "
                                "positive is a credit to the desk)"),
                        "per_lot_night": round(sw.value, 4), "pair": pair.symbol, "side": side}
                else:
                    why = sw.why if not sw.known else (lot_notional.why if not lot_notional.known
                                                       else conv.why)
                    row["funding_price"] = unmeasured(f"{pair.symbol}: {why}").as_dict()
        out[ccy] = row
    return {"account_ccy": a, "legs": out, "n_positions_unpriced": n_unpriced,
            "rule": ("signed notional per currency leg; the funding price of a foreign leg is "
                     "the account-currency pair's own swap, annualised on its notional")}


# ------------------------------------------------------------------------------------ stress


@dataclass(frozen=True)
class Scenario:
    """A named stress: fractional price moves by asset class, by currency (vs USD) and by symbol.

    `status` is DECLARED for a scenario carried as documented public market history and
    MEASURED for one read off the desk's own tape (`symbol_moves` dated per symbol).
    """

    name: str
    provenance: str
    status: str
    horizon_days: float
    class_moves: Mapping[str, float] = field(default_factory=dict)
    #: currency -> fractional move AGAINST USD (+ strengthens); USD itself is the numeraire
    currency_moves: Mapping[str, float] = field(default_factory=dict)
    symbol_moves: Mapping[str, float] = field(default_factory=dict)
    swap_multiplier: float = 1.0
    note: str = ""

    def move_for(self, terms: InstrumentTerms) -> Measure:
        """Fractional move of the instrument's PRICE under this scenario."""
        sym = terms.symbol
        if sym in self.symbol_moves:
            return Measure(float(self.symbol_moves[sym]), self.status, "per-symbol move")
        base, quote = terms.legs()
        if base in CURRENCIES and quote in CURRENCIES and self.currency_moves:
            b = float(self.currency_moves.get(base, 0.0)) if base != "USD" else 0.0
            q = float(self.currency_moves.get(quote, 0.0)) if quote != "USD" else 0.0
            if base in self.currency_moves or quote in self.currency_moves \
                    or "USD" in (base, quote):
                return Measure((1.0 + b) / (1.0 + q) - 1.0, self.status,
                               f"currency legs {base}/{quote}: ({1 + b:.3f}/{1 + q:.3f}) - 1")
        cls = terms.asset_class
        if cls in self.class_moves:
            return Measure(float(self.class_moves[cls]), self.status, f"asset class {cls}")
        return unmeasured(f"{sym}: scenario {self.name} names neither its class "
                          f"{cls!r} nor its currency legs")


SCENARIO_2020_03 = Scenario(
    name="2020-03 pandemic liquidation",
    provenance="PUBLIC_OFFICIAL market history, 2020-02-19 to 2020-03-23 peak-to-trough",
    status=DECLARED, horizon_days=23.0,
    class_moves={"Equities": -0.34, "Indices": -0.34, "Commodities": -0.12,
                 "Energy": -0.55, "Soft Commodity": -0.15, "Crypto": -0.50, "Bonds": 0.05},
    currency_moves={"EUR": -0.04, "GBP": -0.11, "JPY": 0.01, "CHF": 0.00, "AUD": -0.13,
                    "NZD": -0.11, "CAD": -0.09, "NOK": -0.22, "SEK": -0.08, "MXN": -0.24,
                    "ZAR": -0.20, "PLN": -0.10, "HUF": -0.12, "CZK": -0.10, "SGD": -0.04,
                    "TRY": -0.08, "DKK": -0.04, "CNH": -0.02},
    swap_multiplier=1.0,
    note="dash for dollars: every risk currency and every risk asset fell against USD at once")

SCENARIO_2022_RATES = Scenario(
    name="2022 rate shock",
    provenance="PUBLIC_OFFICIAL market history, 2022-01 to 2022-10 (policy rates 0 -> 4%)",
    status=DECLARED, horizon_days=200.0,
    class_moves={"Equities": -0.25, "Indices": -0.25, "Commodities": -0.20, "Energy": 0.40,
                 "Soft Commodity": -0.10, "Crypto": -0.75, "Bonds": -0.20},
    currency_moves={"EUR": -0.16, "GBP": -0.21, "JPY": -0.25, "CHF": -0.09, "AUD": -0.14,
                    "NZD": -0.18, "CAD": -0.08, "NOK": -0.18, "SEK": -0.20, "MXN": 0.02,
                    "ZAR": -0.13, "PLN": -0.20, "HUF": -0.25, "CZK": -0.13, "SGD": -0.06,
                    "TRY": -0.40, "DKK": -0.16, "CNH": -0.13},
    swap_multiplier=3.0,
    note="the swap multiplier is the financing-cost shock: overnight rates tripled or more")


def worst_adverse_move(closes: Sequence[float], side: str, window_bars: int) -> Measure:
    """The worst `window_bars`-bar close-to-close move AGAINST a position of `side`."""
    n = len(closes)
    if n <= window_bars or window_bars <= 0:
        return unmeasured(f"{n} closes is fewer than the {window_bars + 1} needed")
    sign = 1.0 if side.upper() in ("LONG", "BUY") else -1.0
    worst: float | None = None
    for i in range(window_bars, n):
        a, b = float(closes[i - window_bars]), float(closes[i])
        if a <= 0 or not math.isfinite(a) or not math.isfinite(b):
            continue
        r = (b / a - 1.0) * sign
        if worst is None or r < worst:
            worst = r
    if worst is None:
        return unmeasured("no finite closes")
    return measured(worst, f"worst {window_bars}-bar move against a {side.upper()}")


def tape_scenario(name: str, symbol_moves: Mapping[str, float], *, horizon_days: float,
                  provenance: str, swap_multiplier: float = 1.0) -> Scenario:
    """A MEASURED scenario built from per-symbol moves read off the desk's own bars."""
    return Scenario(name=name, provenance=provenance, status=MEASURED,
                    horizon_days=horizon_days, symbol_moves=dict(symbol_moves),
                    swap_multiplier=swap_multiplier)


def margin_call_distance(sheet: BalanceSheet, gross_notional: float | None) -> Measure:
    """The uniform adverse move (fraction of gross notional) that takes margin level to 100%."""
    m = sheet.margin_used
    if not m.known or m.value is None:
        return unmeasured(m.why)
    if gross_notional is None or gross_notional <= 0:
        return unmeasured("no gross notional: an empty or unpriced book has no distance")
    return measured((sheet.equity - m.value) / gross_notional,
                    "(equity - margin) / gross notional")


def stress(sheet: BalanceSheet, positions: Sequence[OpenPosition],
           terms_by_symbol: Mapping[str, InstrumentTerms], rates: Mapping[str, float],
           scenario: Scenario) -> dict[str, Any]:
    """Apply one scenario to the book: P&L, equity, margin, margin level, distance, forced sales.

    FORCED DELEVERAGING, as the venue does it: when the margin level after the shock is below
    the stop-out level, the largest-losing position is closed first and the level re-checked,
    until the book is back above the line. The venue's stop-out is UNMEASURED until read from
    the terminal; when it is, the 100% margin-call line is used instead and the result says so.
    """
    a = sheet.account_ccy
    rows: list[dict[str, Any]] = []
    pnl_total = 0.0
    gross_before = 0.0
    gross_after = 0.0
    margin_before = 0.0
    margin_after = 0.0
    swap_before = 0.0
    n_unpriced = 0
    n_unmeasured_margin = 0
    for p in positions:
        t = terms_by_symbol.get(p.symbol)
        if t is None:
            n_unpriced += 1
            rows.append({"symbol": p.symbol, "sleeve": p.sleeve, "status": UNMEASURED,
                         "why": "no contract terms"})
            continue
        nt = notional_account_ccy(p, t, rates, a)
        mv = scenario.move_for(t)
        if not nt.known or nt.value is None or not mv.known or mv.value is None:
            n_unpriced += 1
            rows.append({"symbol": p.symbol, "sleeve": p.sleeve, "status": UNMEASURED,
                         "why": nt.why if not nt.known else mv.why})
            continue
        pnl = nt.value * mv.value            # signed notional x signed move
        pnl_total += pnl
        gross_before += abs(nt.value)
        gross_after += abs(nt.value) * (1.0 + mv.value)
        mg = margin_required(t, p.lots, p.mark, rates, a)
        if mg.known and mg.value is not None:
            margin_before += mg.value
            # a CFD's margin follows its price; a forex pair's margin is in the base currency
            base, quote = t.legs()
            fx = base in CURRENCIES and quote in CURRENCIES
            margin_after += mg.value if fx else mg.value * (1.0 + mv.value)
        else:
            n_unmeasured_margin += 1
        sw = swap_per_lot_night(t, p.side, p.mark)
        if sw.known and sw.value is not None:
            swap_before += sw.value * abs(p.lots)
        rows.append({"symbol": p.symbol, "sleeve": p.sleeve, "side": p.side, "lots": p.lots,
                     "notional": round(nt.value, 2), "move": round(mv.value, 6),
                     "move_status": mv.status, "pnl": round(pnl, 2), "status": MEASURED})
    equity_after = sheet.equity + pnl_total
    # The margin in use is the terminal's own reading when it has one; rebuilt from the terms
    # otherwise; UNMEASURED when neither is available.
    if sheet.margin_used.known and sheet.margin_used.value is not None:
        m_before = sheet.margin_used.value
        m_after = (m_before * (margin_after / margin_before) if margin_before > 0
                   else m_before)
        margin_src = "terminal margin, scaled by the terms' price sensitivity"
    elif positions and n_unmeasured_margin == 0 and n_unpriced == 0:
        m_before, m_after = margin_before, margin_after
        margin_src = "rebuilt from contract terms and leverage tiers"
    else:
        m_before = m_after = math.nan
        margin_src = "UNMEASURED: no terminal margin and the terms cannot rebuild it"
    level_before = (sheet.equity / m_before * 100.0 if math.isfinite(m_before) and m_before > 0
                    else math.inf if math.isfinite(m_before) else math.nan)
    level_after = (equity_after / m_after * 100.0 if math.isfinite(m_after) and m_after > 0
                   else math.inf if math.isfinite(m_after) else math.nan)
    dist_before = margin_call_distance(sheet, gross_before if n_unpriced == 0 else None)
    after_sheet = BalanceSheet(a, sheet.balance, equity_after,
                               measured(m_after, margin_src) if math.isfinite(m_after)
                               else unmeasured(margin_src), sheet.stop_out_level_pct)
    dist_after = margin_call_distance(after_sheet, gross_after if n_unpriced == 0 else None)
    so = sheet.stop_out_level_pct
    line = so.value if so.known and so.value is not None else MARGIN_CALL_LEVEL_PCT
    line_src = "venue stop-out level" if so.known else "100% margin-call line (stop-out UNMEASURED)"
    forced: list[dict[str, Any]] = []
    eq, mg_now = equity_after, m_after
    if math.isfinite(mg_now) and mg_now > 0 and eq / mg_now * 100.0 < line:
        losing = sorted([r for r in rows if r.get("status") == MEASURED],
                        key=lambda r: float(r["pnl"]))
        for r in losing:
            if mg_now <= 0 or eq / mg_now * 100.0 >= line:
                break
            share = abs(float(r["notional"])) / gross_before if gross_before > 0 else 0.0
            freed = mg_now * share
            forced.append({"symbol": r["symbol"], "sleeve": r["sleeve"],
                           "realised_loss": round(float(r["pnl"]), 2),
                           "margin_freed": round(freed, 2)})
            mg_now -= freed
    return {
        "scenario": scenario.name, "provenance": scenario.provenance,
        "status": scenario.status if n_unpriced == 0 and positions else UNMEASURED,
        "horizon_days": scenario.horizon_days,
        "pnl": round(pnl_total, 2), "equity_before": round(sheet.equity, 2),
        "equity_after": round(equity_after, 2),
        "margin_before": None if not math.isfinite(m_before) else round(m_before, 2),
        "margin_after": None if not math.isfinite(m_after) else round(m_after, 2),
        "margin_source": margin_src,
        "margin_level_before_pct": _pct(level_before), "margin_level_after_pct": _pct(level_after),
        "distance_to_margin_call_before": dist_before.as_dict(),
        "distance_to_margin_call_after": dist_after.as_dict(),
        "swap_per_night_before": round(swap_before, 4),
        "swap_per_night_under_scenario": round(swap_before * scenario.swap_multiplier, 4),
        "margin_call": (math.isfinite(level_after) and level_after < MARGIN_CALL_LEVEL_PCT),
        "forced_deleveraging": {"line_pct": line, "line_source": line_src,
                                "triggered": bool(forced), "closed_in_order": forced},
        "positions": rows, "n_unpriced": n_unpriced,
    }


def _pct(x: float) -> float | None:
    if not math.isfinite(x):
        return None
    return round(x, 2)


# ------------------------------------------------------------------------------------ borrow


def borrow(symbol: str | None = None) -> dict[str, Any]:
    """The securities-borrow leg of a CFD short: UNMEASURED BY CONSTRUCTION, and why.

    There is nothing to measure. A CFD short has no stock borrow, no locate, no rebate and no
    recall; what the desk pays to be short is `swap_short`, which `swap_per_lot_night` prices.
    Returning a number here would be inventing a cost the venue does not charge.
    """
    return {"symbol": symbol, "value": None, "status": "UNMEASURED_BY_CONSTRUCTION",
            "why": ("CFD: no securities-lending leg exists; the cost of a short is entirely in "
                    "swap_short and is priced there, never here")}


# -------------------------------------------------------------------- after-financing growth


def after_financing_growth(gross_log_per_day: float | None, book: Mapping[str, float],
                           financing_cost_r_per_day: Mapping[str, float | None]
                           ) -> dict[str, Any]:
    """The book's geometric return per day after the financing the replay never charged.

    `financing_cost_r_per_day[sleeve]` is the sleeve's swap in R per day (POSITIVE is a cost,
    negative a credit) and `book[sleeve]` its heat, so heat x R/day is account fraction per day
    -- the unit `gross_log_per_day` is in. An UNMEASURED sleeve contributes nothing and is
    counted, which is a different statement from contributing zero.
    """
    drag = 0.0
    n_measured = 0
    n_unmeasured = 0
    by_sleeve: dict[str, float | None] = {}
    for name, h in book.items():
        f = financing_cost_r_per_day.get(name)
        if f is None or not math.isfinite(f):
            n_unmeasured += 1
            by_sleeve[name] = None
            continue
        n_measured += 1
        contrib = float(h) * float(f)
        drag += contrib
        by_sleeve[name] = round(contrib, 8)
    net = None if gross_log_per_day is None else gross_log_per_day - drag
    return {
        "gross_log_per_day": gross_log_per_day,
        "financing_drag_log_per_day": round(drag, 8),
        "after_financing_log_per_day": None if net is None else round(net, 8),
        "after_financing_annual_pct": (None if net is None
                                       else round((math.exp(net * 252.0) - 1.0) * 100.0, 4)),
        "n_sleeves_measured": n_measured, "n_sleeves_unmeasured": n_unmeasured,
        "status": (MEASURED if gross_log_per_day is not None and n_unmeasured == 0 and book
                   else UNMEASURED),
        "by_sleeve": by_sleeve,
        "rule": "sum over sleeves of heat x financing R/day, taken off the gross log growth",
    }


def positions_from_rows(rows: Iterable[Mapping[str, Any]]) -> list[OpenPosition]:
    """OpenPositions from terminal-shaped rows (`type` 0/1 or `side`, `volume`/`lots`)."""
    out: list[OpenPosition] = []
    for r in rows:
        sym = str(r.get("symbol") or "")
        lots = _f(r.get("volume") if r.get("volume") is not None else r.get("lots"))
        po = _f(r.get("price_open"))
        if not sym or lots is None or lots == 0 or po is None or po <= 0:
            continue
        if r.get("side") is not None:
            side = "LONG" if str(r.get("side")).upper() in ("LONG", "BUY", "0") else "SHORT"
        else:
            side = "LONG" if _i(r.get("type")) == 0 else "SHORT"
        out.append(OpenPosition(symbol=sym, side=side, lots=abs(lots), price_open=po,
                                price=_f(r.get("price_current") or r.get("price")),
                                floating_pnl=_f(r.get("profit")), swap_accrued=_f(r.get("swap")),
                                sleeve=str(r.get("sleeve") or r.get("comment") or "")))
    return out
