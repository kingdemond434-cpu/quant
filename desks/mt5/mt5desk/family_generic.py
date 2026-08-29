"""One parameterised family that can express any semantic coordinate. No model writes code.

WHY THIS EXISTS (principal, 2026-08-29: "so all research proposals -- who will implement them")

Nobody did. The free panel emits `NAME | MECHANISM | PAYER | TEST | KILL`; turning that into a
signal function was a human writing Python, and the four edge-queue families were hand-written
today. Every proposal after those would have sat in `hypothesis_queue.jsonl` forever, which is
the same dead end as the queue never existing.

THE OBVIOUS ANSWER IS TO LET A MODEL WRITE THE FAMILY, AND IT IS THE WRONG ONE. Generated code
has to be executed to be tested, and this desk trades real money from the same tree. Hubble
sandboxes an AST allowlist to make that survivable; that is a real engineering programme, and it
buys the ability to express arbitrary logic -- which is not actually what is missing here.

WHAT IS MISSING IS NARROWER. A semantic coordinate has five axes, and almost every mechanism this
desk cares about is the same shape:

    when EVENT happens, in CONTEXT, if QUALITY exceeds a threshold, trade DIRECTION for OUTPUT

That is one function with parameters. `family_generic` implements it, so a proposal becomes a
runnable cell by CHOOSING COORDINATES rather than by emitting code. The search space is bounded
by construction, every cell is inspectable as five names, and nothing a model returns is ever
executed.

WHAT THIS DELIBERATELY CANNOT DO. It cannot express a mechanism that is not of that shape -- a
cross-sectional rank, a multi-leg spread, a term-structure slope. Those still need a hand-written
family, and `compile_proposal` REFUSES them by name rather than approximating. An approximation
would enter the docket as if it were the proposal, and the gauntlet would then judge something
nobody meant to test.

EVERY CELL FACES THE IDENTICAL GAUNTLET. A generic cell has no privilege of any kind. It is worth
less per trial than a hand-written family because it is a coarser expression of the same idea,
and it is worth more than zero because zero is what the alternative produces.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.engine import Signal

#: EVENT -> how the trigger magnitude is computed for each bar. Each returns a series whose
#: absolute value is the "how big was it" the QUALITY axis then thresholds.
#: These are the events the desk can actually observe on H1 bars; anything needing options,
#: order flow or a fixing calendar is absent on purpose rather than approximated.
_EVENTS = {
    "session_transition": lambda d: d["close"] - d["open"],
    "volatility_shock": lambda d: _rng(d) - _rng(d).rolling(20).mean(),
    "liquidity_shock": lambda d: _rng(d) / _rng(d).rolling(20).median(),
    "cross_market_move": lambda d: d["close"].pct_change(4),
    "inventory_rebalance": lambda d: d["close"] - d["close"].rolling(20).mean(),
    "positioning_extreme": lambda d: d["close"] - d["close"].rolling(60).mean(),
    "macro_release": lambda d: d["close"].diff(),
    "carry_change": lambda d: d["close"].pct_change(24),
    "forced_deleveraging": lambda d: d["close"].diff() / (d["high"] - d["low"]).rolling(20).mean(),
    "benchmark_flow": lambda d: d["close"] - d["open"],
    "options_hedging": lambda d: d["close"].diff(),
}

#: CONTEXT -> a boolean mask. Session windows are BROKER hours (Fusion runs UTC+3) because the
#: bars are; converting per-signal is where an off-by-three-hours bug hides for months.
_CONTEXTS = {
    "asia": lambda d: (d.index.hour >= 1) & (d.index.hour < 9),
    "london": lambda d: (d.index.hour >= 9) & (d.index.hour < 17),
    "new_york": lambda d: (d.index.hour >= 15) & (d.index.hour < 23),
    "overlap": lambda d: (d.index.hour >= 15) & (d.index.hour < 17),
    "high_vol": lambda d: _rv(d) > _rv(d).rolling(100).median(),
    "low_vol": lambda d: _rv(d) < _rv(d).rolling(100).median(),
    "high_liquidity": lambda d: _rng(d) < _rng(d).rolling(100).median(),
    "low_liquidity": lambda d: _rng(d) > _rng(d).rolling(100).median(),
    "trend": lambda d: (d["close"] - d["close"].rolling(50).mean()).abs()
                       > _atr(d, 20),
    "range": lambda d: (d["close"] - d["close"].rolling(50).mean()).abs() <= _atr(d, 20),
    "month_end": lambda d: d.index.day >= 26,
}

#: DIRECTION -> sign of the trade relative to the event's sign.
_DIRECTIONS = {
    "continuation": 1,
    "reversal": -1,
    "convergence": -1,
    "divergence": 1,
}

#: OUTPUT -> hold horizon in H1 bars. Sub-hourly horizons are ABSENT rather than rounded to one
#: bar: a 5m claim tested on H1 bars is a different claim, and silently substituting one would
#: put a result in the docket under a coordinate it does not belong to.
_HORIZONS = {"1h": 1, "4h": 4, "daily": 24}


def _rng(d: pd.DataFrame) -> pd.Series:
    """Bar range. Named so the event/context tables read as economics, not as arithmetic."""
    return d["high"] - d["low"]


def _rv(d: pd.DataFrame) -> pd.Series:
    return d["close"].pct_change().rolling(20).std()


def _atr(d: pd.DataFrame, n: int) -> pd.Series:
    prev = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - prev).abs(),
                    (d["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def supported() -> dict[str, list[str]]:
    """Exactly what this family can express. A caller must check before compiling."""
    return {"event": sorted(_EVENTS), "context": sorted(_CONTEXTS),
            "direction": sorted(_DIRECTIONS), "output": sorted(_HORIZONS)}


def family_generic(
    df: pd.DataFrame,
    *,
    event: str = "session_transition",
    context: str = "asia",
    direction: str = "continuation",
    output: str = "1h",
    quality_atr: float = 1.0,
    stop_atr: float = 1.2,
    rr: float = 1.5,
    vol_n: int = 20,
) -> list[Signal]:
    """A semantic coordinate, executed. Unsupported axes return NO signals and never approximate.

    `quality_atr` is the QUALITY axis: how large the event must be, measured in the instrument's
    own ATR so the threshold means the same thing on gold and on EURCHF. An absolute threshold
    would silently become a different test on every symbol.
    """
    if df.empty or len(df) < vol_n * 6:
        return []
    ev_fn = _EVENTS.get(event)
    ctx_fn = _CONTEXTS.get(context)
    sign = _DIRECTIONS.get(direction)
    hold = _HORIZONS.get(output)
    # REFUSE, DO NOT SUBSTITUTE. Falling back to a default axis would run a different experiment
    # under this coordinate's name, and the docket would record the answer to a question nobody
    # asked.
    if ev_fn is None or ctx_fn is None or sign is None or hold is None:
        return []

    d = df.copy()
    atr = _atr(d, vol_n)
    try:
        mag = ev_fn(d)
        mask = ctx_fn(d)
    except (KeyError, ValueError, TypeError):
        return []
    mask = np.asarray(mask, dtype=bool)

    out: list[Signal] = []
    start = vol_n * 6
    for i in range(start, len(d) - 1):
        if not mask[i]:
            continue
        a = float(atr.iloc[i])
        m = float(mag.iloc[i]) if np.isfinite(mag.iloc[i]) else np.nan
        if not np.isfinite(a) or a <= 0 or not np.isfinite(m) or m == 0:
            continue
        # QUALITY: the event must be abnormal in the instrument's own terms.
        if abs(m) < quality_atr * a:
            continue
        side = int(np.sign(m)) * sign
        if side == 0:
            continue
        px = float(d["close"].iloc[i])
        stop = px - side * stop_atr * a
        out.append(Signal(time=d.index[i], side=side, stop=stop,
                          target=px + side * stop_atr * a * rr, ttl_bars=hold,
                          tag=f"generic:{event}|{context}|{direction}|{output}",
                          trigger=None, wait_bars=1))
    return out
