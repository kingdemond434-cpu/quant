"""Backtest engine for the MT5 research desk.

Bar-based, long/short, cost-honest (real measured spread + commission), session-aware.
All times UTC. No lookahead: signals computed on closed bars only, entries at next bar open.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Costs:
    spread_per_lot: float = 0.48
    commission_per_lot: float = 3.50
    contract_oz: float = 100.0

    def per_oz_roundtrip(self) -> float:
        return self.spread_per_lot + self.commission_per_lot * 2.0

    @classmethod
    def from_symbol(cls, m: dict, mult: float = 2.0) -> "Costs":
        """Canonical costs from a universe.json symbol entry.

        spread_per_lot = median_spread_pts * tick_size * contract_size,
        scaled by `mult` as a conservatism factor; commission $3.50/lot/side.
        """
        if not m:
            return cls()
        spread_usd = (
            float(m.get("median_spread_pts", 1.0))
            * float(m.get("tick_size", 0.0))
            * float(m.get("contract_size", 100.0))
        )
        cs = float(m.get("contract_size", 100.0))
        return cls(
            spread_per_lot=max(spread_usd * mult, 0.05),
            commission_per_lot=3.50,
            contract_oz=cs,
        )


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
    idx = df.index.to_numpy()
    # epoch-ns lookups: tz-proof
    idx_ns = idx.astype("datetime64[ns]").astype("int64")
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
        if sig.trigger is not None:
            tgt = sig.trigger
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
        banked = False
        banked_at = 0.0
        trail_ext = entry
        exit_price: float | None = None
        reason = "ttl"
        bars_held = 0
        last = min(len(idx), fill_bar + ttl)
        for j in range(fill_bar, last):
            bars_held = j - fill_bar + 1
            hi, lo = float(h[j]), float(l[j])
            if side > 0:
                if not banked and bank_frac > 0 and hi >= target:
                    banked = True
                    banked_at = target
                    stop = max(stop, entry + abs(entry - sig.stop) * bank_protect_k)
                if banked:
                    trail_ext = max(trail_ext, hi)
                    if runner_trail_k > 0:
                        stop = max(stop, trail_ext - abs(entry - sig.stop) * runner_trail_k)
                if lo <= stop:
                    exit_price, reason = stop, "bank" if banked else "stop"
                    break
                if not banked and hi >= target:
                    exit_price, reason = target, "target"
                    break
            else:
                if not banked and bank_frac > 0 and lo <= target:
                    banked = True
                    banked_at = target
                    stop = min(stop, entry - abs(entry - sig.stop) * bank_protect_k)
                if banked:
                    trail_ext = min(trail_ext, lo)
                    if runner_trail_k > 0:
                        stop = min(stop, trail_ext + abs(entry - sig.stop) * runner_trail_k)
                if hi >= stop:
                    exit_price, reason = stop, "bank" if banked else "stop"
                    break
                if not banked and lo <= target:
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
        r -= per_oz_cost / stop_dist
        trades.append(
            Trade(
                entry_time=pd.Timestamp(idx[fill_bar]),
                exit_time=pd.Timestamp(idx[min(fill_bar + bars_held - 1, len(idx) - 1)]),
                side=side, entry=entry, exit=exit_price,
                stop=sig.stop, target=sig.target,
                bars_held=bars_held, r_multiple=float(r), reason=reason,
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