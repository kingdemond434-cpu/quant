"""The scalp lane's signals as engine `Signal`s: bar by bar, what `plan_entry` would place.

WHY THIS FILE EXISTS. Every cell this desk certifies is judged by ONE gauntlet
(`scripts/external_gauntlet.run_gauntlet`): its daily R series comes out of `engine.run_backtest`
and walks the same ten gates as every other cell. The gauntlet only knew how to build H1 family
cells, so the four gold scalp candidates in `research/scalp_shadow.CANDIDATES` could never hold a
certificate and the promoter had to treat their forward clock as one. A lane with no backtest
gauntlet is a lane whose economics nobody has measured against the same bar as everything else.

This adapter is the missing constructor. For a scalp recipe (family, session, ATR stop/target
geometry, hold) it emits, at every bar where the lane's signal fires, the exact bracket
`mt5desk.scalp_exec.plan_entry` would place at that bar's open -- so the engine replays what the
executor trades, and the ten gates judge that.

THE REPLAY'S CONTRACT, restated for the engine (see `scalp_exec` for the live restatement):

    signal   `scalp_family_expansion._base_signals(bars)[family]` at bar i is built entirely from
             bars <= i-1 (every input is shifted) and masked by bar i's session. The engine fills
             at the open of the first bar strictly after `Signal.time`, so the signal is stamped
             on bar i-1 and the fill is bar i's open -- the replay's `first = open[i]`.
    stop     entry -/+ stop_atr x ATR of the LAST CLOSED bar (i-1), as `scalp_exec.last_closed_atr`.
    target   entry +/- target_atr x that same ATR.
    ttl      `ttl_bars = max_hold + 1`. The engine's time exit fires at the open of bar
             fill + ttl, and that bar's timestamp is exactly `scalp_exec.ttl_deadline` -- the
             close of bar i + max_hold, the replay's own time exit.

DELIBERATE DEVIATIONS FROM `scalp_reverse_engineering.simulate`, stated rather than hidden. Each
one is either the live executor's own rule or the pessimistic direction; none flatters the cell.

  1. ATR of bar i-1, not bar i. `simulate` reads `atr[i]`, which includes bar i's own range and is
     unknowable at bar i's open; `scalp_exec` already documents using the last closed bar's ATR
     and this adapter matches the executor, not the study. A stop the executor could not have
     known is not a stop.
  2. The bracket is live on the fill bar, stop first. `simulate` never examines bar i's high/low;
     live, the stop and target rest from the moment the order fills, so a bar that runs through
     the stop after filling is a loss. The engine checks the fill bar with stop-first ordering --
     the same intrabar pessimism every other cell is judged under.
  3. The time exit is the open of the bar after the hold window, not the close of the last bar in
     it -- the same instant on the clock, one tick apart in price -- and the next entry may not
     fill until the bar after that exit (single-position discipline in the engine), where
     `simulate` re-enters at the very next bar. Fewer trades, never more.
  4. The cost model is the desk's sanctioned one, `Costs.from_symbol` from the universe registry at
     the honest 2x median-spread round trip, not the bar's recorded spread column. That is the
     gauntlet's rule for every cell (`external_gauntlet.costs_for`), and it is what makes the
     scalp cells comparable to the rest of the book.
  5. Single slice, full risk. The engine has no path for the replay's `bounded_structural` basket
     (later quarter-risk slices added at the open of agreeing bars, sharing the stop). The
     certificate therefore covers the `single` arm -- the mode the lane SELECTED on in
     `scalp_family_expansion` -- and the basket is a sizing overlay on the identical signal, stop
     and target that `scalp_exec.slice_lot` already falls back from when a lot cannot be quartered.

`tests/test_scalp_gauntlet.py` measures 1-3 against `simulate` on synthetic bars and pins the
tolerance; the numbers are in the test, not asserted here from memory.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mt5desk.engine import Signal

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: The replay's own warm-up floor: `simulate` starts at `max(40, lookback + 3)` with the lane's
#: lookback of 20. Matched so the adapter never fires a trade the replay could not have taken.
WARMUP_BARS = 40
#: Which signal directions to emit. The certified recipe trades both; the others exist so a
#: caller can measure one leg without editing the signal.
SIDE_MODES: dict[str, tuple[int, ...]] = {"both": (1, -1), "long": (1,), "short": (-1,)}
#: Every timeframe the lane has ever swept, and the sessions the expansion crossed each family
#: with. Named here because the multiplicity census below is derived from them.
SWEPT_TIMEFRAMES: tuple[str, ...] = ("M1", "M5", "M15")
SWEPT_SESSIONS: tuple[str, ...] = ("all", "london", "new_york", "overlap")


def _families() -> Any:
    from desks.mt5.research import scalp_family_expansion as fam
    return fam


def _core() -> Any:
    from desks.mt5.research import scalp_reverse_engineering as core
    return core


def utc_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Sorted, de-duplicated, tz-aware UTC bars -- the shape both the session mask and the engine
    assume. A naive index is localized (the box stamps bars +00:00), an aware one converted."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("scalp bars need a DatetimeIndex")
    out = df.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out.index = (out.index.tz_localize("UTC") if out.index.tz is None
                 else out.index.tz_convert("UTC"))
    return out


def masked_signal(df: pd.DataFrame, family: str, session: str) -> np.ndarray:
    """The lane's signal for `family` under `session`, exactly as the forward clock builds it."""
    fam = _families()
    signals = fam._base_signals(df)
    if family not in signals:
        raise KeyError(f"family {family!r} has no exact executable in scalp_family_expansion")
    sig = np.asarray(signals[family], dtype=np.int8).copy()
    sig[~fam._session_mask(df.index, session)] = 0
    return sig


def family_scalp(df: pd.DataFrame, *, family: str, session: str, stop_atr: float,
                 target_atr: float, max_hold: int, side_mode: str = "both",
                 tag: str | None = None) -> list[Signal]:
    """Engine signals for one scalp recipe: the bracket `plan_entry` would place at each fill.

    Returns one `Signal` per firing bar i, stamped on bar i-1 so the engine fills at bar i's
    open. Bars inside the replay's warm-up, bars whose last-closed ATR is not a positive finite
    number, and the final bar (nothing to fill into) emit nothing -- the same bars `simulate`
    skips, for the same reasons.
    """
    if side_mode not in SIDE_MODES:
        raise ValueError(f"side_mode must be one of {sorted(SIDE_MODES)}, not {side_mode!r}")
    if not (float(stop_atr) > 0 and float(target_atr) > 0 and int(max_hold) >= 1):
        raise ValueError("stop_atr and target_atr must be positive and max_hold >= 1")
    bars = utc_frame(df)
    if len(bars) <= WARMUP_BARS + 1:
        return []
    sig = masked_signal(bars, family, session)
    atr = np.asarray(_core()._atr(bars), dtype=float)
    opens = bars["open"].to_numpy(float)
    allowed = SIDE_MODES[side_mode]
    label = tag or f"{family}/{session}"
    out: list[Signal] = []
    last = len(bars) - 1
    for i in np.flatnonzero(sig != 0):
        i = int(i)
        if i < WARMUP_BARS or i >= last:
            continue
        side = int(sig[i])
        if side not in allowed:
            continue
        a = float(atr[i - 1])
        if not (math.isfinite(a) and a > 0):
            continue
        entry = float(opens[i])
        if not (math.isfinite(entry) and entry > 0):
            continue
        out.append(Signal(
            time=pd.Timestamp(bars.index[i - 1]), side=side,
            stop=entry - side * float(stop_atr) * a,
            target=entry + side * float(target_atr) * a,
            ttl_bars=int(max_hold) + 1, tag=label,
        ))
    return out


def _family_names() -> tuple[str, ...]:
    """Every family the expansion defines, base and anti, counted from the code that defines them.

    A 64-bar synthetic frame is enough: the generator returns a key per family regardless of
    whether any signal fires, and deriving the count this way means a family added to the
    expansion is charged here without anyone remembering to update a literal.
    """
    idx = pd.date_range("2026-01-05", periods=64, freq="15min", tz="UTC")
    flat = pd.DataFrame({"open": 2000.0, "high": 2000.5, "low": 1999.5, "close": 2000.0,
                         "tick_volume": 1.0}, index=idx)
    return tuple(sorted(_families()._base_signals(flat)))


def swept_grid() -> dict[str, Any]:
    """Every configuration the scalp lane has ever swept, derived from the research modules.

    WHY THIS IS COUNTED. The four candidates were not four hypotheses. They are the survivors of
    two searches -- `scalp_reverse_engineering` (the screenshot basket: four mechanisms x two
    stops x two targets x two holds x two implementation modes, on three timeframes) and
    `scalp_family_expansion` (seven families and their seven anti-signals x four sessions x the
    per-timeframe exit geometries, selected in `single` mode and then reported in both modes on the
    untouched 40%). A deflated Sharpe that charges only the four survivors charges the lane for
    the trials it kept, not the trials it ran. The gauntlet charges the sealed fixed campaign
    count (`policy/gate_spec.yaml`, `fixed_trial_count`); `scripts/scalp_gauntlet.py` refuses to
    mint a certificate whenever that charge is below this grid, so the lane can never be judged
    against fewer trials than it spent.

    The mode arm is counted precisely rather than as a full factor: selection ran in `single`
    mode, and the second mode was evaluated once per selected (family, timeframe) on the OOS
    segment. Counting it as a factor over the whole selection grid would double a search that was
    never run; leaving it out would forget the one extra look each winner got.
    """
    core, fam = _core(), _families()
    reverse = {tf: len(core._configs(tf)) for tf in SWEPT_TIMEFRAMES}
    families = _family_names()
    geometry = {tf: len(fam._geometry(tf)) for tf in SWEPT_TIMEFRAMES}
    selection = {tf: len(families) * len(SWEPT_SESSIONS) * geometry[tf]
                 for tf in SWEPT_TIMEFRAMES}
    modes = ("single", "bounded_structural")
    mode_arms = {tf: len(families) * (len(modes) - 1) for tf in SWEPT_TIMEFRAMES}
    total = sum(reverse.values()) + sum(selection.values()) + sum(mode_arms.values())
    return {
        "total": int(total),
        "reverse_engineering": {"per_timeframe": reverse, "total": int(sum(reverse.values()))},
        "family_expansion": {
            "families": len(families), "sessions": len(SWEPT_SESSIONS),
            "geometries_per_timeframe": geometry, "selection_per_timeframe": selection,
            "extra_mode_arms_per_timeframe": mode_arms,
            "total": int(sum(selection.values()) + sum(mode_arms.values())),
        },
        "timeframes": list(SWEPT_TIMEFRAMES),
        "basis": ("reverse_engineering._configs per timeframe + family_expansion families x "
                  "sessions x geometries per timeframe (selection, single mode) + one extra "
                  "mode arm per (family, timeframe) on the untouched segment"),
    }
