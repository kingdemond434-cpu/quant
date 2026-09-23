"""CROSS-FREQUENCY HYPOTHESES: a state clock, a signal clock and an execution clock, declared.

WHAT WAS ACTUALLY MISSING (Tier-1 G17, demoted by external audit 2026-09-09 and closed here).
The desk had the DATA rung -- `refresh_tail` derives `<SYM>_D1.parquet` from H1 and the state
vector picks a series per clock -- and the audit was right that this is not the capability:

    A D1 file is not a D1 -> H1 -> M5 chain. The capability asked for is a hypothesis whose
    state timeframe, signal timeframe and execution timeframe are THREE DECLARED FIELDS,
    searched as such by the sweep, carried through certificate -> forward clock -> gateway.
    Today a cell has ONE timeframe.

So a `CrossFrequencySpec` carries three, and everything below is about the two things that make
three clocks harder than one rather than merely more of it.

THE FIRST IS LOOKAHEAD, AND IT IS THE WHOLE REASON THIS MODULE EXISTS.

A daily state is not knowable while its day is still forming. An H1 bar at 03:00 on the 8th may
use the state of the 7th and NEVER the state of the 8th, because the 8th's daily bar closes
twenty-one hours after that H1 bar has already been traded. The natural implementation --
resample to D1, forward-fill onto the H1 index -- gets this exactly wrong: pandas labels a daily
bar with its OPENING timestamp, so a naive `reindex(..., method="ffill")` hands 03:00 on the 8th
the state of the 8th, which is a full day of hindsight applied to every bar of every day.

That is not a subtle bias. `align_down` is a strict as-of join on the coarse bar's CLOSE time,
and `test_the_naive_alignment_leaks_and_this_one_does_not` plants a state that is pure future
information and shows the naive join scoring it as a perfect edge while this one scores nothing.

THE SECOND IS THAT CONDITIONING IS NOT FREE.

Three rungs multiply the search and divide the sample: a state that fires on 30% of days and a
setup that fires on 10% of hours leaves 3% of the bars, and an edge measured on 3% of a
two-year H1 series is measured on ~150 observations. So every rung reports its own count, the
chain reports the survivors, and `evaluate` REFUSES -- `lift is None` with a filled `why` --
below `MIN_TRIGGERS`. A chain that fires eleven times has not been measured, and saying so is
the difference between a research tool and a random-number generator with a nice interface.

WHAT IT DOES NOT DO. It does not admit, rank or size anything. `evaluate` returns a reading;
the gauntlet decides. The `lift` it reports is the state rung's own contribution -- the edge WITH
the state condition minus the edge without it, on the same signal and the same bars -- because
that difference is the only thing that says whether the coarse clock earned its place. A chain
whose lift is zero is a one-clock hypothesis wearing three, and it costs three clocks' worth of
multiplicity to say so.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "MIN_TRIGGERS",
    "TIMEFRAMES",
    "ChainReading",
    "CrossFrequencySpec",
    "RungReading",
    "align_down",
    "bar_minutes",
    "evaluate",
    "is_coarser",
]

#: The clocks a spec may name, coarsest first. A chain must go coarse -> fine, which is what
#: makes it a chain: a state on a FINER clock than its signal is not a state, it is a second
#: signal, and reading it as a state would let a five-minute wiggle gate an hourly setup.
TIMEFRAMES: tuple[str, ...] = ("W1", "D1", "H4", "H1", "M30", "M15", "M5", "M1")

_MINUTES: dict[str, int] = {"W1": 7 * 24 * 60, "D1": 24 * 60, "H4": 240, "H1": 60,
                            "M30": 30, "M15": 15, "M5": 5, "M1": 1}

#: Triggers below which a chain is UNMEASURED rather than weak. Three rungs shrink a sample fast
#: and the shrinkage is invisible in the summary statistic; this is the floor that makes it
#: visible. Chosen to match `causal_graph.MIN_STATE_N` (60), the smallest bucket this desk
#: already reports a conditional statistic on.
MIN_TRIGGERS = 60


def bar_minutes(tf: str) -> int:
    """Minutes in one bar of `tf`. Raises on a clock this desk does not derive."""
    try:
        return _MINUTES[str(tf).upper()]
    except KeyError:
        raise ValueError(f"unknown timeframe {tf!r}; this desk derives {TIMEFRAMES}") from None


def is_coarser(a: str, b: str) -> bool:
    """Is `a` a strictly coarser clock than `b`?"""
    return bar_minutes(a) > bar_minutes(b)


def align_down(coarse: pd.Series, fine_index: pd.DatetimeIndex, *,
               bar: str) -> pd.Series:
    """Carry a coarse-clock series onto a fine index using only bars that had CLOSED.

    THE POINT-IN-TIME RULE, AND THE ONE LINE THIS MODULE IS FOR. A bar labelled `t` on a clock
    of `bar` minutes covers `[t, t + bar)` and is not knowable until `t + bar`. So the value a
    fine bar at time `u` may use is the last coarse value whose CLOSE is `<= u` -- strictly, the
    last one with `t + bar <= u`.

    `pd.merge_asof` with `allow_exact_matches=True` on the shifted close times gives exactly
    that: a daily bar that closes at midnight is available to the 00:00 H1 bar and not before.
    The value is NaN until the first coarse bar has closed, which is correct and is why the
    caller must drop rather than fill.

    The naive alternative -- `coarse.reindex(fine_index, method="ffill")` -- matches on the
    coarse bar's OPENING label and therefore hands every bar of a day that day's own outcome.
    """
    if not isinstance(coarse, pd.Series):
        raise TypeError("coarse must be a pandas Series indexed by bar open time")
    if len(coarse) == 0 or len(fine_index) == 0:
        return pd.Series(np.nan, index=fine_index, dtype="float64")
    closes = pd.DatetimeIndex(coarse.index) + pd.Timedelta(minutes=bar_minutes(bar))
    left = pd.DataFrame({"_t": pd.DatetimeIndex(fine_index)}).sort_values("_t")
    right = pd.DataFrame({"_t": closes, "_v": np.asarray(coarse.to_numpy(), dtype="float64")})
    right = right.sort_values("_t")
    merged = pd.merge_asof(left, right, on="_t", direction="backward",
                           allow_exact_matches=True)
    out = pd.Series(merged["_v"].to_numpy(), index=merged["_t"].to_numpy(), dtype="float64")
    return out.reindex(pd.DatetimeIndex(fine_index))


@dataclass(frozen=True)
class CrossFrequencySpec:
    """Three clocks and the rule each one applies. The three fields the audit asked for.

    `state` is a callable over the STATE-clock frame returning a boolean Series on that frame's
    index; `signal` is the same over the SIGNAL-clock frame. `exec_tf` is where the resulting
    trade is executed and is carried so a certificate, a forward clock and the gateway all read
    one declared chart rather than inferring one -- the defect `executables.executor_gap`
    already guards for single-clock cells.

    The clocks must be ordered coarse -> fine, checked at construction. `exec_tf` equal to
    `signal_tf` is allowed (execute on the bar you signalled on); coarser is not.
    """

    state_tf: str
    signal_tf: str
    exec_tf: str
    state: Callable[[pd.DataFrame], pd.Series]
    signal: Callable[[pd.DataFrame], pd.Series]
    name: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for tf in (self.state_tf, self.signal_tf, self.exec_tf):
            bar_minutes(tf)                                   # raises on an underived clock
        if not is_coarser(self.state_tf, self.signal_tf):
            raise ValueError(
                f"state clock {self.state_tf} must be strictly coarser than the signal clock "
                f"{self.signal_tf}: a state on a finer clock is a second signal, and reading it "
                f"as a state lets a wiggle gate a setup")
        if bar_minutes(self.exec_tf) > bar_minutes(self.signal_tf):
            raise ValueError(
                f"execution clock {self.exec_tf} is coarser than the signal clock "
                f"{self.signal_tf}: the trade cannot be placed on a bar that closes after the "
                f"one that signalled it")

    @property
    def clocks(self) -> tuple[str, str, str]:
        return (self.state_tf, self.signal_tf, self.exec_tf)


@dataclass(frozen=True)
class RungReading:
    """One rung's own count, so a chain that vanished says WHERE it vanished."""

    clock: str
    bars: int
    fired: int

    @property
    def rate(self) -> float | None:
        return (self.fired / self.bars) if self.bars else None

    def to_dict(self) -> dict[str, Any]:
        return {"clock": self.clock, "bars": self.bars, "fired": self.fired, "rate": self.rate}


@dataclass(frozen=True)
class ChainReading:
    """What the chain measured, or why it refused.

    `lift is None` IS the refusal. `edge_with` is the mean forward return on bars where BOTH
    the state and the signal hold; `edge_without` is the same signal on bars where the state
    does NOT hold. `lift` is their difference -- the state rung's own contribution, which is the
    only number that says whether the coarse clock earned its multiplicity.
    """

    spec_name: str
    clocks: tuple[str, str, str]
    rungs: tuple[RungReading, ...]
    triggers: int = 0
    edge_with: float | None = None
    edge_without: float | None = None
    lift: float | None = None
    why: str = ""
    min_triggers: int = MIN_TRIGGERS

    def __bool__(self) -> bool:
        return self.lift is not None

    def to_dict(self) -> dict[str, Any]:
        return {"spec": self.spec_name, "clocks": list(self.clocks),
                "rungs": [r.to_dict() for r in self.rungs], "triggers": self.triggers,
                "edge_with": self.edge_with, "edge_without": self.edge_without,
                "lift": self.lift, "why": self.why, "min_triggers": self.min_triggers}


def _refused(spec: CrossFrequencySpec, rungs: Sequence[RungReading], why: str,
             triggers: int = 0) -> ChainReading:
    return ChainReading(spec_name=spec.name, clocks=spec.clocks, rungs=tuple(rungs),
                        triggers=triggers, why=why)


def _boolean(out: Any, index: pd.Index, what: str) -> pd.Series:
    s = pd.Series(out)
    if len(s) != len(index):
        raise ValueError(f"{what} returned {len(s)} rows for {len(index)} bars")
    return pd.Series(np.asarray(s.to_numpy(), dtype="bool"), index=index)


def evaluate(spec: CrossFrequencySpec, frames: dict[str, pd.DataFrame], *,
             horizon: int = 1, min_triggers: int = MIN_TRIGGERS,
             price: str = "close") -> ChainReading:
    """Measure one cross-frequency chain. Returns a reading; admits nothing.

    `frames` maps each clock the spec names to its bars, indexed by bar OPEN time. The forward
    return is taken on the EXECUTION clock over `horizon` of its bars, because that is the trade
    the chain would actually place -- measuring it on the signal clock would price a hold the
    execution clock never takes.

    REFUSES, never guesses: a missing frame, a rung that fires on nothing, and a survivor count
    below `min_triggers` each come back with `lift is None` and a `why` that names the rung.
    """
    rungs: list[RungReading] = []
    for tf in dict.fromkeys(spec.clocks):
        if tf not in frames or frames[tf] is None or len(frames[tf]) == 0:
            return _refused(spec, rungs, f"no bars for the {tf} clock this chain declares")
    state_df, signal_df = frames[spec.state_tf], frames[spec.signal_tf]
    exec_df = frames[spec.exec_tf]
    if price not in exec_df.columns:
        return _refused(spec, rungs, f"the {spec.exec_tf} frame has no {price!r} column")

    state_raw = _boolean(spec.state(state_df), state_df.index, "state")
    rungs.append(RungReading(spec.state_tf, len(state_df), int(state_raw.sum())))
    if not int(state_raw.sum()):
        return _refused(spec, rungs, f"the state rule never held on the {spec.state_tf} clock")

    signal_raw = _boolean(spec.signal(signal_df), signal_df.index, "signal")
    rungs.append(RungReading(spec.signal_tf, len(signal_df), int(signal_raw.sum())))
    if not int(signal_raw.sum()):
        return _refused(spec, rungs, f"the signal rule never held on the {spec.signal_tf} clock")

    # THE STATE COMES DOWN ONLY WHERE IT HAD CLOSED. NaN until the first coarse bar closes.
    on_signal = align_down(state_raw.astype("float64"), pd.DatetimeIndex(signal_df.index),
                           bar=spec.state_tf)
    known = on_signal.notna()
    held = known & (on_signal > 0.5)

    # The trade is placed on the execution clock at the first bar at or after the signal bar's
    # own close -- the same rule, one rung down, so a signal never executes inside its own bar.
    sig_closes = pd.DatetimeIndex(signal_df.index) + pd.Timedelta(
        minutes=bar_minutes(spec.signal_tf))
    exec_index = pd.DatetimeIndex(exec_df.index)
    pos = exec_index.searchsorted(sig_closes, side="left")
    px = np.asarray(exec_df[price].to_numpy(), dtype="float64")
    fwd = np.full(len(signal_df), np.nan)
    ok = (pos >= 0) & (pos + horizon < len(exec_index))
    entry = np.where(ok, px[np.clip(pos, 0, len(px) - 1)], np.nan)
    exit_ = np.where(ok, px[np.clip(pos + horizon, 0, len(px) - 1)], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        fwd = np.where(ok & (entry > 0), (exit_ - entry) / entry, np.nan)

    usable = np.isfinite(fwd) & signal_raw.to_numpy() & known.to_numpy()
    with_mask = usable & held.to_numpy()
    without_mask = usable & ~held.to_numpy()
    triggers = int(with_mask.sum())
    rungs.append(RungReading(spec.exec_tf, int(usable.sum()), triggers))
    if triggers < int(min_triggers):
        return _refused(spec, rungs,
                        f"{triggers} bars survive all three rungs, below the floor of "
                        f"{int(min_triggers)}: three clocks divide a sample fast and an edge "
                        f"measured on this many observations is not measured",
                        triggers=triggers)
    edge_with = float(np.mean(fwd[with_mask]))
    edge_without = (float(np.mean(fwd[without_mask])) if int(without_mask.sum()) else None)
    return ChainReading(
        spec_name=spec.name, clocks=spec.clocks, rungs=tuple(rungs), triggers=triggers,
        edge_with=edge_with, edge_without=edge_without,
        lift=(None if edge_without is None else edge_with - edge_without),
        why=("the state rule held on every usable signal bar, so there is nothing to compare it "
             "against" if edge_without is None else ""),
        min_triggers=int(min_triggers))
