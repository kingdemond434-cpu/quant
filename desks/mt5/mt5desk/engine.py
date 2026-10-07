"""Backtest engine for the MT5 research desk.

Bar-based, long/short, cost-honest (real measured spread + commission), session-aware.
All times UTC. No lookahead: signals computed on closed bars only, entries at next bar open.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

#: MT5 ENUM_SYMBOL_SWAP_MODE, all nine values. THE UNIT OF `swap_long`/`swap_short` LIVES IN THIS
#: FIELD, NOT IN THE NUMBER (found 2026-10-07). `from_symbol` read every registry swap as POINTS;
#: 138 of the 248 swap-carrying symbols are mode 5, where the broker quotes an ANNUAL PERCENT of
#: notional -- a dimension error, not a factor, on 55% of the universe and on every LIVE symbol
#: that is an index, a share or a metal CFD. Mode 0 is DISABLED, not points.
SWAP_MODE_DISABLED = 0
SWAP_MODE_POINTS = 1
SWAP_MODE_CURRENCY_SYMBOL = 2      # money in the symbol's BASE currency
SWAP_MODE_CURRENCY_MARGIN = 3      # money in the symbol's MARGIN currency
SWAP_MODE_CURRENCY_DEPOSIT = 4     # money in the ACCOUNT's currency
SWAP_MODE_INTEREST_CURRENT = 5     # annual % of notional at the CURRENT price
SWAP_MODE_INTEREST_OPEN = 6        # annual % of notional at the position's OPEN price
SWAP_MODE_REOPEN_CURRENT = 7       # position re-opened at the close price +/- N points
SWAP_MODE_REOPEN_BID = 8           # position re-opened at the bid +/- N points
SWAP_MODES: dict[int, str] = {
    0: "DISABLED", 1: "POINTS", 2: "CURRENCY_SYMBOL", 3: "CURRENCY_MARGIN",
    4: "CURRENCY_DEPOSIT", 5: "INTEREST_CURRENT", 6: "INTEREST_OPEN", 7: "REOPEN_CURRENT",
    8: "REOPEN_BID"}
#: Day-count basis for the interest modes. THE SAME DECLARED CONVENTION as
#: `research/carry_state.DAY_COUNT` (a test pins the two equal): a broker convention this desk has
#: not read from the terminal, and the earlier of the two candidates is the one that charges more.
SWAP_DAY_COUNT = 360.0
#: The swap_mode of each symbol as the venue's contract-terms tape recorded it, resolved per
#: symbol by `research/carry_state.py`. Read ONLY when the registry row carries no `swap_mode` of
#: its own; `universe_registry.cost_fields_from_symbol_info` now writes the field on the box.
_SWAP_MODE_SOURCE = Path(__file__).resolve().parent.parent / "data" / "carry_state.json"


@dataclass(frozen=True)
class Costs:
    """Round-trip cost in ACCOUNT CURRENCY PER LOT, not per unit.

    THE UNIT ON spread_per_lot IS THE WHOLE TRAP, AND IT COST THIS DESK A LOT

    per_oz_roundtrip() adds the spread to two commissions and the engine then
    divides by contract_size. For that to come out as a price-unit cost,
    spread_per_lot must be the spread MULTIPLIED BY contract size -- currency
    per lot, matching the field name and matching commission_per_lot beside it.

    Every JPY call site did that: median_spread_pts * tick_size * contract_size,
    which divides straight back down to the true spread. Every gold call site
    passed a hardcoded 0.48, and run_hunt6's docstring says why -- "XAUUSD
    overridden to the measured live spread 0.48", which is 3x the measured
    0.16/oz median written as dollars PER OUNCE into a field that wants dollars
    per lot. The engine divided it by 100 and charged gold 0.0048/oz: three
    percent of its real spread.

    So every gold backtest on this desk has run very nearly spread-free, and the
    3x cost-stress gate meant to catch exactly this was stressing 3% up to 9%.
    Use from_symbol() rather than hand-rolling the arithmetic at the call site.
    """
    spread_per_lot: float = 16.0
    # MEASURED, not published: 2.00 in ACCOUNT CURRENCY per lot per side, over all 433
    # deals the live Fusion account has ever done (reports/COST_TRUTH.json 2026-09-23, with
    # p10 = p50 = p90 = 2.00 and no exception on any of the twelve traded symbols, gold
    # included). The 2.25 here was the brochure's USD figure sitting in a field this
    # class converts as ACCOUNT currency through `quote_per_account` -- the same unit
    # trap the comment below describes, one level up. See fusion_cost.COMMISSION_UNIT.
    commission_per_lot: float = 2.00
    contract_oz: float = 100.0
    #: PRICE UNITS PER UNIT OF ACCOUNT CURRENCY, per lot -- the second unit trap, found
    #: 2026-08-26. `spread_per_lot` round-trips correctly because it was built as
    #: `pts * tick_size * contract_size` and the engine divides by contract_size again, landing
    #: back on a price-unit spread. `commission_per_lot` does NOT: it is a currency amount, and
    #: dividing it by contract_size treats one unit of the account's currency as one unit of
    #: PRICE. That is only true when the symbol is quoted in the account's own currency.
    #:
    #: On a EUR account, CADJPY prices in yen: one yen of price is worth 0.005418 EUR, so a
    #: 7.00 EUR round-turn commission is 0.01292 yen of price -- and the engine was charging
    #: 7.00/100000 = 0.00007. 184x too little, on the JPY crosses where this desk's surviving
    #: edges actually live, in the direction that manufactures survivors.
    #:
    #: Defaults to 1.0, which is exactly today's arithmetic, so no existing call site changes
    #: silently. `from_symbol()` sets it from tick_value and is the only correct constructor.
    quote_per_account: float = 1.0
    #: OVERNIGHT FINANCING PER LOT PER NIGHT, in the same convention as `spread_per_lot`
    #: (points x tick_size x contract_size), found missing 2026-09-15.
    #:
    #: THE ENGINE CHARGED ZERO SWAP ON EVERY CERTIFICATE THIS DESK HAS EVER MINTED. Grep this
    #: module before the change and "swap" returns nothing. For an intraday sleeve that is
    #: correct and costs nothing; for `overnight_gap_decay`, which holds through rollover BY
    #: CONSTRUCTION, the one cost that dominates the family was never charged.
    #:
    #: AND THE NUMBER WAS ALREADY ON DISK. `universe.json` carries `swap_long`/`swap_short` for
    #: 248 of 251 symbols and has since the registry was built -- the same shape as
    #: `strategy_paths`, where the data sat one directory over while the desk recorded that it
    #: could not be measured. `from_symbol()` reads it; nothing else has to.
    #:
    #: THE WORSE SIDE, ALWAYS. A sleeve may be long or short and the desk does not get to pick
    #: the cheaper financing after the fact. GBPMXN pays -324.72 points long against +39.11
    #: short: charging the favourable side prices a trade the book cannot guarantee it is taking.
    #:
    #: Defaults to 0.0, which is exactly today's arithmetic, so no existing call site re-prices
    #: silently -- the same discipline `quote_per_account` and `spread_pts` document above, and
    #: for the same reason: this class is on the money path.
    swap_per_lot_per_night: float = 0.0
    #: THE PRICE-LINKED PART OF THE NIGHTLY CHARGE, per lot per UNIT OF PRICE, in the same
    #: convention as `swap_per_lot_per_night`. A night costs
    #: `swap_per_lot_per_night + swap_per_lot_per_price * price`. Set for swap_mode 5 and 6
    #: (`contract * pct / 100 / SWAP_DAY_COUNT`) and for a base/margin-currency amount that has to
    #: be carried into the quote currency at the price (modes 2/3 on a pair). None for every other
    #: mode -- and None is not a number, so `sleeve_registry.cost_hash` (numeric fields only) is
    #: unchanged for every symbol whose charge did not change.
    swap_per_lot_per_price: float | None = None
    #: Which price a price-linked night is charged at: "rollover" (the close of the last bar
    #: before each rollover instant -- modes 5, 2, 3) or "open" (the entry price -- mode 6).
    swap_price_basis: str | None = None
    #: WHY THE FINANCING COULD NOT BE PRICED, by name, or None. When set both swap fields are
    #: zero and this string is the verdict: UNMEASURED, never a clean zero (L1.28a), and never a
    #: points reading of a number whose unit is unknown.
    swap_unmeasured: str | None = None

    def per_oz_roundtrip(self) -> float:
        """Round-trip cost per lot, in the convention the engine divides by `contract_oz`.

        The commission is converted from account currency into that convention; the spread is
        already in it. See `quote_per_account`.

        SWAP IS NOT HERE ON PURPOSE. Spread and commission are paid ONCE per round trip and are
        constants of the trade; financing is paid PER NIGHT and is a function of how long the
        trade was held. Folding it into a round-trip constant would charge a scalp the same
        financing as a week-long hold. See `financing()`.
        """
        return (self.spread_per_lot
                + self.commission_per_lot * 2.0 * float(self.quote_per_account))

    def financing(self, nights: float, price_nights: float | None = None) -> float:
        """Overnight financing for `nights` rollovers, in the `per_oz_roundtrip` convention.

        `price_nights` is the sum, over the rollovers charged, of the price each one is charged
        at (a triple night counting its price three times) -- see `rollover_price_nights`. It is
        REQUIRED when the cost model is price-linked (swap_mode 5/6, or 2/3 on a pair): a mode-5
        rate without a price is an annual percent of nothing, and charging zero for it is the
        silent-zero this field exists to end, so it raises instead.
        """
        fixed = float(self.swap_per_lot_per_night) * float(nights)
        if not self.swap_per_lot_per_price:
            return fixed
        if price_nights is None:
            raise ValueError("price-linked swap (swap_per_lot_per_price set) needs price_nights")
        return fixed + float(self.swap_per_lot_per_price) * float(price_nights)

    @property
    def charges_swap(self) -> bool:
        """True when any overnight financing is priced into this cost model."""
        return bool(self.swap_per_lot_per_night) or bool(self.swap_per_lot_per_price)

    def stressed(self, spread_mult: float) -> Costs:
        """A cost-stress variant of THIS cost model -- widen the spread, keep everything else.

        THE DEFECT THIS CLOSES, measured live 2026-08-27 on the certificate path. Every stress
        scenario on this desk rebuilt `Costs(...)` positionally from three fields of an existing
        one, so the FOURTH field -- `quote_per_account` -- silently reverted to its 1.0 default.
        That default exists so adding the field moved no existing call site; in a re-derivation it
        instead un-does the conversion the baseline already applied. `universal_gate`'s x3
        scenario on CADJPY: baseline round trip 1699.29, "x3" as written 607.00, x3 correct
        1899.29. The gate built to prove a candidate survives THREE TIMES its costs was testing
        it at 0.36x -- strictly weaker than the baseline it is supposed to stress, on the JPY
        crosses where this desk's live family actually sits.

        Deriving with `replace` makes the whole class unreachable: a field added later is carried
        by construction, and no call site has to remember it. Commission is deliberately NOT
        scaled -- it is contractual and does not widen with market stress, so multiplying it
        models nothing that happens (see `from_symbol`).
        """
        return replace(self, spread_per_lot=self.spread_per_lot * float(spread_mult))

    @classmethod
    def from_symbol(cls, meta: dict[str, Any], mult: float = 1.0,
                    commission_per_lot: float = 2.00, *,
                    spread_pts: float | None = None) -> Costs:
        """Costs for one symbol from its universe.json metadata.

        `mult` scales the SPREAD ONLY. Commission is contractual and does not
        widen, so stressing it models nothing that happens. mult=2.0 is the
        honest baseline rather than a stress: a round trip crosses the spread on
        the way in and again on the way out, and a median is a median -- half of
        all fills are worse than it.

        `spread_pts` OVERRIDES `median_spread_pts` with a spread the caller measured for the
        state it is actually trading in -- in practice the fill hour, from
        `desks/mt5/research/cost_surface.py`. The third unit trap, found 2026-08-29: that
        registry field is the median over ALL hours, and spread is not a constant of a symbol.
        Measured on this desk's own tape, `family_overnight_gap_decay` fills at broker hour 01
        (its signal is the first bar of the day and `wait_bars=1` moves the fill on by one), a
        book carrying ~3% of the day's peak tick volume: USDZAR's pooled 329 pts against 2,028
        pts on its own fill bars, EURZAR's 310 against 1,918 -- 6.2x, with the p90 at 17-20x.
        Re-priced at the fill-hour spread with `mult` held equal on both arms, both sleeves --
        certified, and on live forward clocks -- go from +0.25R to NEGATIVE.

        It defaults to None, which reproduces today's arithmetic exactly, so no existing call
        site changes silently. That is the same discipline `quote_per_account` documents above,
        and for the same reason: this class is on the money path and a default that moves an
        existing number is a silent re-pricing of the live book.

        None is also what the surface returns for a cell it has not MEASURED, and the fallback
        to the pooled scalar there is deliberate and is the honest one -- it leaves the caller
        exactly where it is today rather than inventing a number. `check_cost_surface.py` is
        what stops that fallback becoming invisible: it reports the cell UNMEASURED rather than
        OK (L1.28a), so an unpriced hour is a named gap and not a clean verdict.
        """
        cs = float(meta.get("contract_size", 1e5))
        ts = float(meta.get("tick_size", 0.0))
        pts = (float(spread_pts) if spread_pts is not None
               else float(meta.get("median_spread_pts", 0.0)))
        spread = pts * ts * cs
        # PRICE UNITS PER UNIT OF ACCOUNT CURRENCY. `tick_value` is one tick's worth in account
        # currency for one lot, so `cs * ts / tick_value` is how many price units one unit of
        # account currency buys -- 1.0 for a symbol quoted in the account's own currency, ~185
        # for a JPY cross on a EUR account. WITHOUT tick_value there is no conversion and the
        # commission would silently revert to the 184x undercharge, so its absence falls back to
        # 1.0 and is REPORTED rather than assumed away: see scripts/check_universe_registry.py.
        tv = float(meta.get("tick_value", 0.0) or 0.0)
        qpa = (cs * ts / tv) if (tv > 0 and cs > 0 and ts > 0) else 1.0
        # FINANCING, FROM THE REGISTRY THE DESK ALREADY KEEPS, IN THE UNIT ITS swap_mode NAMES.
        # Until 2026-10-07 every swap was read as POINTS (`pts * tick_size * contract_size`),
        # which is right for mode 1 and a dimension error for the 138 mode-5 symbols, whose
        # number is an annual percent of notional. `swap_model` converts every MT5 mode into the
        # convention `spread_per_lot` uses; the worse side is charged, see
        # `swap_per_lot_per_night`. A symbol with no swap fields charges zero (it has no rate);
        # a symbol whose MODE cannot be established is UNMEASURED by name, never points.
        fixed, per_price, basis, why = swap_model(meta, cs=cs, ts=ts, qpa=qpa, tv=tv)
        return cls(spread_per_lot=max(spread * mult, 0.05),
                   commission_per_lot=commission_per_lot, contract_oz=cs,
                   quote_per_account=qpa,
                   swap_per_lot_per_night=fixed,
                   swap_per_lot_per_price=per_price,
                   swap_price_basis=basis,
                   swap_unmeasured=why)


@lru_cache(maxsize=1)
def _recorded_swap_modes() -> dict[str, int]:
    """symbol -> swap_mode from the contract-terms reading `carry_state.json` resolved. {} if absent."""
    try:
        data = json.loads(_SWAP_MODE_SOURCE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = data.get("symbols") if isinstance(data, dict) else None
    out: dict[str, int] = {}
    if isinstance(rows, dict):
        for sym, row in rows.items():
            if isinstance(row, dict) and row.get("swap_mode") is not None:
                try:
                    out[str(sym).upper()] = int(row["swap_mode"])
                except (TypeError, ValueError):
                    continue
    return out


def swap_mode_of(meta: dict[str, Any]) -> tuple[int | None, str]:
    """(swap_mode, where it came from). The registry row's own field wins; then the venue's
    recorded contract terms for that symbol; otherwise (None, why) -- the unit is UNKNOWN."""
    raw = meta.get("swap_mode")
    if raw is not None:
        try:
            return int(raw), "registry"
        except (TypeError, ValueError):
            return None, f"registry swap_mode {raw!r} is not an integer"
    sym = str(meta.get("symbol") or "").upper()
    if sym:
        mode = _recorded_swap_modes().get(sym)
        if mode is not None:
            return mode, "contract_terms (carry_state.json)"
    return None, "no swap_mode on the registry row or in the recorded contract terms"


def swap_model(meta: dict[str, Any], *, cs: float, ts: float, qpa: float,
               tv: float) -> tuple[float, float | None, str | None, str | None]:
    """(fixed, per_price, basis, unmeasured) for one symbol's WORSE swap side, per lot per night.

    Every amount is in the convention `spread_per_lot` uses -- quote (profit) currency per lot, so
    `/ contract_size` lands on price units -- and a night costs `fixed + per_price * price`:

        0 DISABLED          0
        1 POINTS            swap * point * contract                       (point == tick_size)
        2 CURRENCY_SYMBOL   base-currency money -> quote: x1 when base == profit, x price on a pair
        3 CURRENCY_MARGIN   margin-currency money -> quote: x1 if margin == profit, x price if
                            margin == base on a pair
        4 CURRENCY_DEPOSIT  account money * quote_per_account (needs tick_value)
        5 INTEREST_CURRENT  price * contract * pct / 100 / SWAP_DAY_COUNT, at each night's price
        6 INTEREST_OPEN     the same rate at the position's OPEN price
        7 REOPEN_CURRENT    re-opened at the close +/- N points: N points of price per night, so
        8 REOPEN_BID        the money is the POINTS formula (the re-open price move IS the charge)

    The mode comes from `swap_mode_of`. An unknown or unresolvable mode returns
    (0.0, None, None, reason) -- UNMEASURED by name, never read as points.
    """
    lo = float(meta.get("swap_long", 0.0) or 0.0)
    sh = float(meta.get("swap_short", 0.0) or 0.0)
    worse = max(abs(lo), abs(sh))
    if worse == 0.0:
        return 0.0, None, None, None
    mode, src = swap_mode_of(meta)
    if mode is None:
        return 0.0, None, None, f"UNMEASURED: swap unit unknown ({src})"
    if mode == SWAP_MODE_DISABLED:
        return 0.0, None, None, None
    if mode in (SWAP_MODE_POINTS, SWAP_MODE_REOPEN_CURRENT, SWAP_MODE_REOPEN_BID):
        if ts <= 0 or cs <= 0:
            return 0.0, None, None, f"UNMEASURED: mode {mode} needs tick_size and contract_size"
        return worse * ts * cs, None, None, None
    if mode in (SWAP_MODE_INTEREST_CURRENT, SWAP_MODE_INTEREST_OPEN):
        if cs <= 0:
            return 0.0, None, None, f"UNMEASURED: mode {mode} needs contract_size"
        basis = "rollover" if mode == SWAP_MODE_INTEREST_CURRENT else "open"
        return 0.0, cs * worse / 100.0 / SWAP_DAY_COUNT, basis, None
    if mode == SWAP_MODE_CURRENCY_DEPOSIT:
        if not (tv > 0 and ts > 0 and cs > 0):
            return 0.0, None, None, "UNMEASURED: mode 4 needs tick_value to leave account currency"
        return worse * qpa, None, None, None
    if mode in (SWAP_MODE_CURRENCY_SYMBOL, SWAP_MODE_CURRENCY_MARGIN):
        profit = str(meta.get("currency_profit") or "").upper()
        base = str(meta.get("currency_base") or "").upper()
        ccy = base if mode == SWAP_MODE_CURRENCY_SYMBOL else str(
            meta.get("currency_margin") or "").upper()
        if ccy and profit and ccy == profit:
            return worse, None, None, None
        if ccy and base and profit and ccy == base and base != profit:
            return 0.0, worse, "rollover", None
        return 0.0, None, None, (f"UNMEASURED: mode {mode} money is in {ccy or '?'}, which is "
                                 f"neither the profit ({profit or '?'}) nor the base currency "
                                 "of a pair, so there is no price to carry it into quote")
    return 0.0, None, None, f"UNMEASURED: swap_mode {mode} is not an MT5 swap mode"


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: int
    entry: float
    exit: float
    stop: float
    target: float
    bars_held: int
    r_multiple: float
    reason: str
    units: float = 1.0  # total size held at exit, in initial-unit multiples
    adds: int = 0       # pyramid adds that actually filled


@dataclass
class Signal:
    time: pd.Timestamp
    side: int
    stop: float
    target: float
    ttl_bars: int
    tag: str
    trigger: float | None = None  # intrabar stop-order level (breakouts); None = next open
    wait_bars: int = 1  # bars the resting trigger stays alive (1 = next bar only)
    bank_frac: float = 0.0  # 0 = flat target exit; >0 = close this fraction at target, rest runs
    bank_protect_k: float = 0.0  # runner stop moves to entry + stop_dist*k after bank (0 = BE)
    runner_trail_k: float = 0.0  # 0 = fixed stop; >0 = chandelier trail at stop_dist*k off extreme
    # --- stall-conditioned tightening. A trail that STAYS wide bleeds: on a
    # pullback entry after a strong run, a static chandelier at k=4 lost $16.82
    # an ounce over 95 events while the same k tightened to 1 after three bars
    # without a new extreme MADE $9.80. Paired against the whole static family
    # on identical events the difference is +$11.63/oz, better 63% of the time,
    # t = 2.48 -- one hypothesis, so no deflation is owed.
    #
    # The mechanism is not "a better constant". Breathing room and profit
    # protection are wanted at DIFFERENT TIMES: while the move is still
    # printing new extremes, and once it has stopped. `runner_trail_k` alone
    # cannot say that, so it was a constant answering a question with two
    # answers. Note the effect is ~nil (t = 1.11) on entries taken at the high:
    # this pays for a pullback entry and does not rescue a chase.
    trail_tighten_k: float = 0.0  # 0 = never tighten; else k once stalled
    trail_stall_bars: int = 0     # bars with no new extreme before tightening
    # --- winner pyramiding: exposure grows only after the market has PROVED the
    # thesis, which is the opposite of averaging down and must never be confused
    # with it. Add k fills at entry + side*k*add_every_r*stop_dist.
    add_every_r: float = 0.0   # 0 = no adds; else spacing between adds, in R
    add_max: int = 0           # hard cap on the number of adds
    add_frac: float = 0.0      # size of each add relative to the initial unit
    # After add k the stop for the WHOLE stack moves to the (k-1)th add level --
    # breakeven on the first add. Without this the stack's open risk grows with
    # every add, which is how a pyramid turns into the thing it is not supposed
    # to be. Set False only to MEASURE that difference, never to trade it.
    add_ratchets_stop: bool = True


@dataclass
class BacktestResult:
    trades: list[Trade]
    signal_count: int
    equity: float = 0.0

    @property
    def n(self) -> int:
        return len(self.trades)

    def stats(self) -> dict[str, float]:
        if not self.trades:
            return {
                "n": 0, "expectancy_r": 0.0, "t_stat": 0.0, "profit_factor": 0.0,
                "win_rate": 0.0, "avg_win_r": 0.0, "avg_loss_r": 0.0, "max_dd_r": 0.0,
            }
        rs = np.array([t.r_multiple for t in self.trades])
        wins = rs[rs > 0]
        losses = rs[rs < 0]
        n = len(rs)
        mean = rs.mean()
        sd = rs.std(ddof=1) if n > 1 else 0.0
        t_stat = mean / (sd / np.sqrt(n)) if sd > 0 else 0.0
        pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
        cum = np.cumsum(rs)
        peak = np.maximum.accumulate(cum)
        max_dd = float((cum - peak).min())
        return {
            "n": n, "expectancy_r": float(mean), "t_stat": float(t_stat),
            "profit_factor": float(pf),
            "win_rate": float((rs > 0).mean()),
            "avg_win_r": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss_r": float(losses.mean()) if len(losses) else 0.0,
            "max_dd_r": max_dd,
        }


#: UTC hour of the broker's rollover. Fusion's server runs UTC+2 in winter and UTC+3 in summer,
#: so server midnight is 22:00 UTC or 21:00 UTC. 21 is used and the choice is deliberately the
#: EARLIER one: it can only count a rollover a position did not quite reach, never miss one it
#: paid. A cost model that errs must err expensive.
ROLLOVER_HOUR_UTC = 21
#: Weekday whose rollover carries three days' financing, because its value date spans the
#: weekend. Monday=0, so 2 is Wednesday -- the standard FX convention on every retail venue.
TRIPLE_SWAP_WEEKDAY = 2


def rollovers_between(t0: pd.Timestamp, t1: pd.Timestamp) -> float:
    """Financing nights charged for a position held from `t0` to `t1`.

    WHY THIS IS NOT `(t1 - t0).days`. A trade opened 20:00 and closed 22:00 crosses ONE rollover
    and pays a full night on two hours of exposure; a trade opened 22:00 and closed the next
    18:00 crosses NONE and pays nothing on twenty hours. Financing is charged at an INSTANT, not
    pro rata, and a duration-based charge gets both of those backwards.

    Wednesday's rollover counts three, which is not a detail: it is 43% of a week's financing on
    one instant, and the families that hold through a Wednesday night pay it every week.

    A naive timestamp is read as UTC. That is the same assumption the rest of this engine makes
    of the universe parquets, and stating it here keeps it from being made twice differently.
    """
    if t0 is None or t1 is None:
        return 0.0
    a, b = pd.Timestamp(t0), pd.Timestamp(t1)
    if a.tzinfo is not None:
        a = a.tz_convert("UTC").tz_localize(None)
    if b.tzinfo is not None:
        b = b.tz_convert("UTC").tz_localize(None)
    if not (b > a):
        return 0.0
    # The first rollover instant strictly after the entry.
    cur = a.normalize() + pd.Timedelta(hours=ROLLOVER_HOUR_UTC)
    if cur <= a:
        cur = cur + pd.Timedelta(days=1)
    if cur > b:
        return 0.0
    # COUNTED, NOT WALKED. The rollover instants are cur, cur+1d, ..., the last one <= b: that is
    # `k` of them, and each is one night plus two more when it falls on the triple-swap weekday.
    # This was a Python loop of Timestamp additions, one per night per trade, and on the sealed
    # gauntlet's build path it cost more than the bar loop it sits under; the count below is the
    # same integer (so the same float), with no loop.
    k = int((b - cur) // pd.Timedelta(days=1)) + 1
    first_triple = (TRIPLE_SWAP_WEEKDAY - cur.weekday()) % 7
    triples = 0 if first_triple >= k else 1 + (k - 1 - first_triple) // 7
    return float(k + 2 * triples)


def rollover_price_nights(idx_ns: np.ndarray, px: np.ndarray, first_bar: int, last_bar: int,
                          t0: pd.Timestamp, t1: pd.Timestamp) -> float:
    """Sum of the price each rollover between `t0` and `t1` is charged at, triples counting three.

    THE PRICE OF A NIGHT IS THE PRICE AT THAT NIGHT. A mode-5 rate is an annual percent of the
    position's CURRENT notional, so each rollover is charged at the close of the last bar that
    opened strictly before the rollover instant, held inside [first_bar, last_bar]. The instants
    and their weights are exactly the ones `rollovers_between` counts, so with a constant price
    this returns `rollovers_between(t0, t1) * price`.
    """
    if t0 is None or t1 is None:
        return 0.0
    a, b = pd.Timestamp(t0), pd.Timestamp(t1)
    if a.tzinfo is not None:
        a = a.tz_convert("UTC").tz_localize(None)
    if b.tzinfo is not None:
        b = b.tz_convert("UTC").tz_localize(None)
    if not (b > a):
        return 0.0
    cur = a.normalize() + pd.Timedelta(hours=ROLLOVER_HOUR_UTC)
    if cur <= a:
        cur = cur + pd.Timedelta(days=1)
    if cur > b:
        return 0.0
    k = int((b - cur) // pd.Timedelta(days=1)) + 1
    inst = cur.value + np.arange(k, dtype="int64") * (86_400 * 10**9)
    weekday = (cur.weekday() + np.arange(k)) % 7
    w = np.where(weekday == TRIPLE_SWAP_WEEKDAY, 3.0, 1.0)
    pos = np.searchsorted(idx_ns, inst, side="left") - 1
    pos = np.clip(pos, first_bar, last_bar)
    return float(np.sum(w * px[pos].astype(float)))


def run_backtest(
    df: pd.DataFrame,
    signals: list[Signal],
    costs: Costs,
    max_hold_bars: int | None = None,
) -> BacktestResult:
    """Simulate trades from signals against an OHLC frame (index = UTC).

    Entries fill at the open of the first bar strictly after the signal time.
    Stops checked intrabar via low/high; targets similarly. TTL and max-hold
    force exits. Position closed at next bar open if no stop/target hit.
    """
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    # The price a rollover is charged at (price-linked swap modes only): the bar's close.
    close_px = df["close"].to_numpy() if "close" in df.columns else o
    # KEEP THE PANDAS INDEX. `df.index.to_numpy()` on a tz-AWARE index returns an object array
    # of Timestamps and warns "no explicit representation of timezones available for
    # np.datetime64" -- benign in production, but under `filterwarnings = error` it turns the
    # look-ahead guards into failures, and it is the kind of implicit coercion that would quietly
    # strip the clock off `entry_time` if numpy ever chose datetime64 instead. Indexing a
    # DatetimeIndex yields the same tz-aware Timestamps with nothing implicit about it.
    idx = df.index
    # epoch-ns lookups: tz-proof. `asi8` is UTC epoch-ns for an aware index and wall-clock ns for
    # a naive one, which is exactly what the previous astype chain produced for each.
    # UNIT-PROOF, NOT JUST TZ-PROOF. `asi8` returns the index's OWN resolution: nanoseconds for
    # datetime64[ns], but MILLISECONDS for datetime64[ms] -- and `pd.Timestamp(...).value` below
    # is always nanoseconds. A producer rewrote every universe parquet with a ms-resolution index
    # (2026-08-27), so `searchsorted` compared 1.52e12 against 1.52e18 and placed EVERY signal
    # past the end of the array: locs == len(idx) for all of them, every signal discarded as
    # out-of-range, ZERO trades from 4,360 valid signals -- silently, on every cell, on both
    # boxes. It read downstream as "this cell has too few observations to judge", which is how it
    # survived: the gauntlet dropped 118 of 122 cells as untestable and nothing said why.
    # `as_unit("ns")` pins the comparison to one resolution regardless of what wrote the file.
    idx_ns = np.asarray(pd.DatetimeIndex(idx).as_unit("ns").asi8, dtype="int64")
    sig_ns = np.array(
        [pd.Timestamp(s.time).value for s in signals], dtype="int64"
    )
    locs = np.searchsorted(idx_ns, sig_ns)
    trades: list[Trade] = []
    filled = 0
    per_oz_cost = costs.per_oz_roundtrip() / costs.contract_oz
    last_exit_idx = -1  # single-position discipline: no overlapping trades

    for sig, i0 in zip(signals, locs, strict=True):
        i = i0 + 1
        if i <= 0 or i >= len(idx) - 1:
            continue
        if i <= last_exit_idx:
            continue
        entry = float(o[i])
        if entry != entry or not (entry > 0):
            continue
        # intrabar trigger fill: a resting stop order that lives `wait_bars` bars
        fill_bar = i
        limit_entry = False
        if sig.trigger is not None:
            tgt = sig.trigger
            # A LIMIT entry sits on the far side of the market from the trade's
            # direction (buy below, sell above); a STOP entry sits beyond it.
            # The distinction is inferred rather than declared so it also covers
            # the families that predate this field.
            limit_entry = ((sig.side > 0 and tgt < entry)
                           or (sig.side < 0 and tgt > entry))
            hit = -1
            for j in range(i, min(i + sig.wait_bars, len(idx))):
                if float(h[j]) >= tgt >= float(lows[j]):
                    hit = j
                    break
            if hit < 0:
                continue
            fill_bar = hit
            entry = float(tgt)
        side = sig.side
        stop = sig.stop
        target = sig.target
        ttl = sig.ttl_bars
        bank_frac = sig.bank_frac
        bank_protect_k = sig.bank_protect_k
        runner_trail_k = sig.runner_trail_k
        trail_tighten_k = sig.trail_tighten_k
        trail_stall_bars = sig.trail_stall_bars
        banked = False
        banked_at = 0.0
        trail_ext = entry
        stall = 0
        exit_price: float | None = None
        reason = "ttl"
        bars_held = 0
        sd0 = abs(entry - sig.stop)          # the initial risk unit; R is measured in it
        add_every_r = sig.add_every_r
        add_max = sig.add_max
        add_frac = sig.add_frac
        adds: list[float] = []               # fill prices of the pyramid adds
        pyramid = add_every_r > 0 and add_max > 0 and add_frac > 0 and sd0 > 0
        last = min(len(idx), fill_bar + ttl)
        for j in range(fill_bar, last):
            bars_held = j - fill_bar + 1
            hi, lo = float(h[j]), float(lows[j])
            # THE STOP IS EVALUATED FIRST, against the level in force at bar
            # open, and an add can only fill on a bar the stop survived. Within
            # one OHLC bar the path is unknown, so this denies the pyramid a
            # mid-bar stop ratchet that would have turned a full loss into a
            # breakeven. It biases the measurement AGAINST pyramiding, which is
            # the direction a test of pyramiding has to be biased.
            if side > 0:
                if (not banked and bank_frac > 0 and hi >= target
                        and not (limit_entry and j == fill_bar)):
                    banked = True
                    banked_at = target
                    stop = max(stop, entry + sd0 * bank_protect_k)
                # THE STOP IS CHECKED BEFORE THIS BAR'S EXTREME FEEDS THE TRAIL.
                # The trail used to ratchet on the bar's own high and then be
                # tested against that same bar's low, so a bar that printed a
                # new high and then collapsed was paid at the RATCHETED stop --
                # the engine resolving unknown intrabar order in the trade's
                # favour. It is the fill-bar leak wearing a different hat, and
                # it is the ordering the pyramid path already refuses ("denies
                # the pyramid a mid-bar stop ratchet"), so the trail was the
                # inconsistent one. It also disagreed with the research that
                # motivated stall-tightening, which checked the low first --
                # the engine would have scored the policy better than the study
                # that justified it, which is how a t = 9.16 gets born.
                if lo <= stop:
                    exit_price, reason = stop, "bank" if banked else "stop"
                    break
                # Trail with no bank leg is now expressible: `bank_frac == 0`
                # used to mean no trail at all, which made a pure runner
                # impossible to write down.
                if banked or bank_frac <= 0:
                    if hi > trail_ext:
                        trail_ext, stall = hi, 0
                    else:
                        stall += 1
                    k = runner_trail_k
                    if trail_tighten_k > 0 and stall >= trail_stall_bars:
                        k = trail_tighten_k
                    if k > 0:
                        stop = max(stop, trail_ext - sd0 * k)
                if pyramid:
                    while len(adds) < add_max:
                        lvl = entry + sd0 * add_every_r * (len(adds) + 1)
                        if hi < lvl:
                            break
                        adds.append(lvl)
                        if sig.add_ratchets_stop:
                            # whole stack ratchets to the PREVIOUS add level:
                            # breakeven on the first add, then trailing behind
                            prev = entry + sd0 * add_every_r * (len(adds) - 1)
                            stop = max(stop, prev)
                # THE FILL BAR MAY NOT PAY A LIMIT ENTRY. We were filled because
                # this bar's LOW reached down to the order; crediting the same
                # bar's HIGH with the target assumes the high came after the
                # fill, and on a down bar it did not. Measured on GBPJPY
                # fair-value-gap: 59.7% of trades resolved on the fill bar,
                # 1022 targets against 713 stops, carrying E[R] +0.283 against
                # +0.105 for everything that resolved later. The stop stays
                # live on this bar -- being wrong in the pessimistic direction
                # is the only safe way to be wrong about intrabar order.
                if not banked and hi >= target and not (limit_entry and j == fill_bar):
                    exit_price, reason = target, "target"
                    break
            else:
                if (not banked and bank_frac > 0 and lo <= target
                        and not (limit_entry and j == fill_bar)):
                    banked = True
                    banked_at = target
                    stop = min(stop, entry - sd0 * bank_protect_k)
                if hi >= stop:            # stop first — see the long side
                    exit_price, reason = stop, "bank" if banked else "stop"
                    break
                if banked or bank_frac <= 0:
                    if lo < trail_ext:
                        trail_ext, stall = lo, 0
                    else:
                        stall += 1
                    k = runner_trail_k
                    if trail_tighten_k > 0 and stall >= trail_stall_bars:
                        k = trail_tighten_k
                    if k > 0:
                        stop = min(stop, trail_ext + sd0 * k)
                if pyramid:
                    while len(adds) < add_max:
                        lvl = entry - sd0 * add_every_r * (len(adds) + 1)
                        if lo > lvl:
                            break
                        adds.append(lvl)
                        if sig.add_ratchets_stop:
                            prev = entry - sd0 * add_every_r * (len(adds) - 1)
                            stop = min(stop, prev)
                if not banked and lo <= target and not (limit_entry and j == fill_bar):
                    exit_price, reason = target, "target"
                    break
        if exit_price is None:
            exit_idx = min(fill_bar + ttl, len(idx) - 1)
            exit_price = float(o[exit_idx])
            reason = "ttl"
            bars_held = exit_idx - fill_bar + 1
        last_exit_idx = min(fill_bar + bars_held - 1, len(idx) - 1)
        stop_dist = abs(entry - sig.stop)
        if stop_dist <= 0:
            continue
        if banked:
            r = bank_frac * (banked_at - entry) / stop_dist * side \
                + (1.0 - bank_frac) * (exit_price - entry) / stop_dist * side
        else:
            r = (exit_price - entry) / stop_dist * side
        # Each add is its own position: its P&L runs from ITS fill price, not
        # the original entry, and it pays its own full round trip. Charging one
        # round trip for a three-unit stack is the same class of error as the
        # 0.48 spread -- it makes a costly mechanism look free.
        units = 1.0
        for fill_px in adds:
            r += add_frac * (exit_price - fill_px) / stop_dist * side
            units += add_frac
        r -= per_oz_cost * units / stop_dist
        # FINANCING, PER NIGHT ACTUALLY CROSSED. Zero for every intraday sleeve, which is why
        # this changes nothing for the scalp lane and is decisive for the overnight one. It is
        # charged on the whole stack (`units`), the same size the spread is charged on.
        # Each bar's Timestamp is boxed ONCE per trade and shared by the financing count and the
        # trade record (it was boxed twice each); a Timestamp is immutable, so sharing it is free.
        entry_ts = pd.Timestamp(idx[fill_bar])
        exit_ts = pd.Timestamp(idx[min(fill_bar + bars_held - 1, len(idx) - 1)])
        # PRICE-AWARE for the interest modes (5/6) and a pair's base/margin money (2/3): those
        # nights are charged at the price of THAT night, or at the entry for mode 6.
        if costs.charges_swap:
            nights = rollovers_between(entry_ts, exit_ts)
            if nights:
                price_nights = None
                if costs.swap_per_lot_per_price:
                    if costs.swap_price_basis == "open":
                        price_nights = nights * entry
                    else:
                        price_nights = rollover_price_nights(
                            idx_ns, close_px, fill_bar,
                            min(fill_bar + bars_held - 1, len(idx) - 1), entry_ts, exit_ts)
                r -= (costs.financing(nights, price_nights) / costs.contract_oz) \
                    * units / stop_dist
        trades.append(
            Trade(
                entry_time=entry_ts,
                exit_time=exit_ts,
                side=side, entry=entry, exit=exit_price,
                stop=sig.stop, target=sig.target,
                bars_held=bars_held, r_multiple=float(r), reason=reason,
                units=float(units), adds=len(adds),
            )
        )
        filled += 1

    return BacktestResult(trades=trades, signal_count=len(signals))


def walk_forward_splits(n_bars: int, folds: int = 4) -> list[tuple[int, int, int, int, int]]:
    """Train start/end, validation end, and untouched-OOS start/end boundaries."""
    per = n_bars // (folds + 1)
    out = []
    for k in range(folds):
        train_end = per * (k + 1)
        val_end = train_end + per
        oos_start = val_end
        out.append((0, train_end, val_end, oos_start, n_bars))
    return out
