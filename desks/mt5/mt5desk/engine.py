"""Backtest engine for the MT5 research desk.

Bar-based, long/short, cost-honest (real measured spread + commission), session-aware.
All times UTC. No lookahead: signals computed on closed bars only, entries at next bar open.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd


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
    # Fusion Zero's published contract is USD 2.25 per lot per side ($4.50 round turn).
    commission_per_lot: float = 2.25
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

    def per_oz_roundtrip(self) -> float:
        """Round-trip cost per lot, in the convention the engine divides by `contract_oz`.

        The commission is converted from account currency into that convention; the spread is
        already in it. See `quote_per_account`.
        """
        return (self.spread_per_lot
                + self.commission_per_lot * 2.0 * float(self.quote_per_account))

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
    def from_symbol(cls, meta: dict, mult: float = 1.0,
                    commission_per_lot: float = 2.25) -> Costs:
        """Costs for one symbol from its universe.json metadata.

        `mult` scales the SPREAD ONLY. Commission is contractual and does not
        widen, so stressing it models nothing that happens. mult=2.0 is the
        honest baseline rather than a stress: a round trip crosses the spread on
        the way in and again on the way out, and a median is a median -- half of
        all fills are worse than it.
        """
        cs = float(meta.get("contract_size", 1e5))
        ts = float(meta.get("tick_size", 0.0))
        spread = float(meta.get("median_spread_pts", 0.0)) * ts * cs
        # PRICE UNITS PER UNIT OF ACCOUNT CURRENCY. `tick_value` is one tick's worth in account
        # currency for one lot, so `cs * ts / tick_value` is how many price units one unit of
        # account currency buys -- 1.0 for a symbol quoted in the account's own currency, ~185
        # for a JPY cross on a EUR account. WITHOUT tick_value there is no conversion and the
        # commission would silently revert to the 184x undercharge, so its absence falls back to
        # 1.0 and is REPORTED rather than assumed away: see scripts/check_universe_registry.py.
        tv = float(meta.get("tick_value", 0.0) or 0.0)
        qpa = (cs * ts / tv) if (tv > 0 and cs > 0 and ts > 0) else 1.0
        return cls(spread_per_lot=max(spread * mult, 0.05),
                   commission_per_lot=commission_per_lot, contract_oz=cs,
                   quote_per_account=qpa)


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
    l = df["low"].to_numpy()
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

    for sig, i0 in zip(signals, locs):
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
                if float(h[j]) >= tgt >= float(l[j]):
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
            hi, lo = float(h[j]), float(l[j])
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
        trades.append(
            Trade(
                entry_time=pd.Timestamp(idx[fill_bar]),
                exit_time=pd.Timestamp(idx[min(fill_bar + bars_held - 1, len(idx) - 1)]),
                side=side, entry=entry, exit=exit_price,
                stop=sig.stop, target=sig.target,
                bars_held=bars_held, r_multiple=float(r), reason=reason,
                units=float(units), adds=len(adds),
            )
        )
        filled += 1

    return BacktestResult(trades=trades, signal_count=len(signals))


def walk_forward_splits(n_bars: int, folds: int = 4) -> list[tuple[int, int, int]]:
    """train / validation / untouched-OOS index triples over the bar count."""
    per = n_bars // (folds + 1)
    out = []
    for k in range(folds):
        train_end = per * (k + 1)
        val_end = train_end + per
        oos_start = val_end
        out.append((0, train_end, val_end, oos_start, n_bars))
    return out
