"""ADVERSARIAL SYNTHETIC REGIMES -- eleven worlds the tape never printed, run at every sleeve.

Quant Scientist item Q5, principal 2026-09-16.

THE HOLE THIS FILLS. Every gate this desk owns judges a rule against HISTORY: the ten gates, the
forward clocks, the lockbox, the cost stress. History is the only honest evidence there is, and it
has one blind spot no amount of it can close -- it cannot falsify a dependency it never varied. A
sleeve that needs the spread to stay where it was, needs the Monday gap to be there, needs its
instrument to move on its own rather than with everything else, or needs the fill to land on
exactly the bar the clock assumed, shows a clean record for as long as those four things hold.
They held for the whole sample. That is not evidence the sleeve does not depend on them; it is the
absence of the experiment.

So this organ runs the experiment. Each scenario is a NAMED, REPLAYABLE, SEEDED transform of a
sleeve's bars and/or its cost model -- same seed, same world, on any box -- and the sleeve is
re-decided and re-filled inside it. The signals are recomputed on the transformed tape on purpose:
the world changed, so the family gets to change its mind.

ONLY A FAILURE IS A FINDING, and the rule rides on the artifact so it cannot be read off. A sleeve
that earns MORE inside a synthetic world has learned nothing -- the world is invented, so its
profit is invented, and ranking on it would be optimising against a random-number generator with a
good name. Nothing here produces a score, a rank or a merit.

WHAT THIS ORGAN NEVER DOES (GROWTH GOVERNANCE, and it is load-bearing). It does not size, cap,
shrink, veto, retire, pause or re-heat anything. It writes one report. Rule 1 says every risk
reduction must first prove it raises robust forward E[log W]; a measurement that reduces nothing
owes no such proof, and it must stay that way -- the moment a flag here is wired to a cap, that
cap needs its own missed-growth ledger line and its own proof. A flag is a QUESTION for research
and for the ten gates ("is this edge the gap, or the tape?"), never an instruction to trade
smaller. Timid is not risk-aware.

THE ELEVEN WORLDS (`SCENARIOS` carries each one's full definition, and so does the artifact)

    usd_shock_liquidity_crash  -3% dollar basket over 4 bars, spreads x4, volume halved
    spread_x5                  the round trip charged at five times the registry's spread
    correlations_to_one        own return replaced by a COMMON shock + 20% own noise
    instant_trend_break        the prevailing 60-bar trend sign-flipped at one random bar
    central_bank_surprise      +/-2.5 sigma jump at a calendar hour, spread x3 for 6 bars
    vol_doubling               returns scaled x2 around their rolling mean
    weekend_gap                a +/-1.5% gap inserted at every Monday open
    weekend_gap_removed        the inverse -- every Monday gap FLATTENED
    feed_latency               executable prices shifted one bar against the signal bars
    partial_fills              30% of entries filled at half size -- R scaled, not dropped
    missing_releases           10% of bars dropped, in blocks of six

THE SIX NAMED FAILURE MODES, each against the same sleeve's baseline on the untouched tape:
`dies_under_spread_x5` (expectancy turns negative), `collapses_when_correlated` (same, under one
common shock), `needs_weekend_gap`, `fill_artefact`, `fragile_to_missing_data` and
`trend_break_sensitive` (each: more than half the expectancy gone). The other scenarios are
measured and published WITHOUT a flag -- naming a threshold nobody asked for would invent a
verdict, and `partial_fills` is a SIZE effect by construction (halving 30% of fills takes ~15% of
expectancy) rather than a structural one.

UNMEASURED IS A VERDICT (L1.28a, L1.49). A scenario that could not touch this tape -- no Monday
opens in the sample, no trend to flip, no calendar hour present, too few bars -- is UNMEASURED for
that sleeve and its flag is NOT evaluated. "The transform ran and nothing fell" and "the transform
never ran" produce the same numbers and mean opposite things, and a gate that never ran is a claim
the desk cannot cash. Same at the sleeve level: absent bars, a family in neither registry (the
gold windows carry their rule in the gateway, not in a registry family), unresolvable inputs, or a
baseline that takes no trades -- all UNMEASURED by name, never a clean row.

BASIS. `mt5desk.engine.run_backtest` + `Costs.from_symbol` when importable, labelled "engine" --
the same replay and cost model the gauntlet mints certificates with, because a failure mode
measured by a second engine is a measurement of the second engine. Otherwise a minimal next-open /
stop / target / TTL replay labelled "minimal_replay", on every row: it models no resting trigger,
banking, trailing or pyramiding, so a sleeve that uses them is measured coarser than it trades and
the row says so instead of implying parity.

BOUNDED, because this box also holds the live terminal: `--max-sleeves` (25) least-recently-tested
first from `data/synthetic_regimes_state.json`, and 90 seconds of wall per sleeve after which the
remaining scenarios are UNMEASURED with the budget named. Rotation is stamped on ATTEMPT, not on
success, so a permanently unmeasurable sleeve cannot pin the queue against everything behind it.

THE ASSUMPTIONS, WRITTEN DOWN RATHER THAN IMPLIED. (1) The engine charges ONE constant round trip,
so a window-local widening cannot be expressed in the cost model: `usd_shock_liquidity_crash`
charges its x4 across the whole replay and is therefore harsher than the event it names, while
`central_bank_surprise` widens only the per-bar spread COLUMN (which the families that read it can
see) and leaves the charge at baseline, so it stays a test of the jump and not a second spread
test. (2) The dollar shock reaches an instrument through its dollar leg: full move, sign +1 where
USD is the quote (EURUSD, XAUUSD rise as the dollar falls), -1 where it is the base; a cross with
no dollar leg gets HALF the move, because this desk has not measured that beta and inventing one
would be worse than naming the assumption. (3) Every transform reprices open/high/low/close by one
positive per-bar factor, so OHLC ordering survives by construction.

    python desks/mt5/research/synthetic_regimes.py [--dry-run] [--max-sleeves 25] [--seed 0]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVES = DESK / "data" / "sleeves.json"
STATE = DESK / "data" / "synthetic_regimes_state.json"
REPORT = DESK / "reports" / "SYNTHETIC_REGIMES.json"

RULE = "synthetic profit is never a merit; only a failure mode is a finding"
MAX_SLEEVES = 25
BUDGET_S = 90.0
#: Bars below this and a transform is measuring its own edge effects, not the sleeve's.
MIN_BARS = 300

#: flag -> (scenario, test). "sign": expectancy turns negative. "half": more than half of it gone.
FLAG_RULES: dict[str, tuple[str, str]] = {
    "dies_under_spread_x5": ("spread_x5", "sign"),
    "collapses_when_correlated": ("correlations_to_one", "sign"),
    "needs_weekend_gap": ("weekend_gap_removed", "half"),
    "fill_artefact": ("feed_latency", "half"),
    "fragile_to_missing_data": ("missing_releases", "half"),
    "trend_break_sensitive": ("instant_trend_break", "half"),
}


# ---------------------------------------------------------------- small shared plumbing

def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> Any:
    """Tolerant read: a BOM, an unreadable file or malformed JSON all answer None, never a guess."""
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def _key(text: str) -> int:
    """A stable 64-bit digest of a name. `hash()` is salted per process; this is not, so the same
    sleeve draws the same world tomorrow and on the other box."""
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


def _rng(seed: int, scenario: str, name: str) -> np.random.Generator:
    return np.random.default_rng([int(seed), _key(scenario), _key(name)])


_M64 = np.uint64(0xFFFFFFFFFFFFFFFF)


def _splitmix(z: np.ndarray) -> np.ndarray:
    z = (z + np.uint64(0x9E3779B97F4A7C15)) & _M64
    z = ((z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)) & _M64
    z = ((z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)) & _M64
    return z ^ (z >> np.uint64(31))


def _common_shock(index: pd.Index, seed: int) -> np.ndarray:
    """Unit-variance normals keyed by the BAR TIMESTAMP, so `correlations_to_one` means it.

    Drawing from a per-sleeve generator would give every instrument its own "common" shock, which
    is the opposite of the scenario's name. Keying on the timestamp makes two instruments that
    trade the same hour receive the SAME shock -- one world, many sleeves -- while staying a pure
    function of (seed, time) and therefore reproducible in any order, on any box.
    """
    ns = np.asarray(pd.DatetimeIndex(index).as_unit("ns").asi8, dtype="int64").astype("uint64")
    k = ns ^ np.uint64(_key(f"common_shock/{int(seed)}"))
    scale = 1.0 / 9007199254740992.0
    u1 = (_splitmix(k) >> np.uint64(11)).astype("float64") * scale
    u2 = (_splitmix(k ^ np.uint64(0xA5A5A5A5A5A5A5A5)) >> np.uint64(11)).astype("float64") * scale
    u1 = np.clip(u1, 1e-12, 1.0)
    return np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)


# ---------------------------------------------------------------- bar transforms

def _logret(df: pd.DataFrame) -> np.ndarray:
    c = np.asarray(df["close"], dtype="float64")
    r = np.zeros(len(c), dtype="float64")
    if len(c) > 1:
        with np.errstate(divide="ignore", invalid="ignore"):
            r[1:] = np.diff(np.log(np.maximum(c, 1e-12)))
    return np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)


def _reprice(df: pd.DataFrame, factor: np.ndarray) -> pd.DataFrame:
    """Scale every price column of every bar by one POSITIVE factor.

    OHLC sanity is preserved by construction -- scaling all four legs of a bar by the same
    positive number cannot reorder them -- which is why every return-changing scenario in this
    module is expressed as a factor path rather than as a hand-edited high or low.
    """
    out = df.copy()
    f = np.asarray(factor, dtype="float64")
    for col in ("open", "high", "low", "close"):
        if col in out.columns:
            out[col] = np.asarray(out[col], dtype="float64") * f
    return out


def _from_returns(df: pd.DataFrame, new_r: np.ndarray) -> pd.DataFrame:
    """Rebuild bars whose close-to-close log returns are `new_r`, keeping each bar's own shape."""
    return _reprice(df, np.exp(np.cumsum(new_r - _logret(df))))


def _scale_col(df: pd.DataFrame, col: str, lo: int, hi: int, k: float) -> int:
    """Multiply `col` over [lo, hi) by k. Returns how many rows were touched (0 = column absent)."""
    if col not in df.columns or hi <= lo:
        return 0
    vals = np.asarray(df[col], dtype="float64")
    vals[lo:hi] *= k
    df[col] = vals
    return int(hi - lo)


def _usd_sign(symbol: str) -> float:
    s = str(symbol).upper()
    if s.startswith("USD") and len(s) >= 6:
        return -1.0
    if s.endswith("USD"):
        return 1.0
    return 0.5


def _monday_opens(index: pd.Index) -> np.ndarray:
    """Positions of the first bar of each week -- a real Monday open, or the first bar after any
    gap of more than a day, which is the same event on a tape the broker closed."""
    idx = pd.DatetimeIndex(index)
    if len(idx) < 2:
        return np.zeros(0, dtype="int64")
    dow = idx.dayofweek.to_numpy()
    gap = np.zeros(len(idx), dtype=bool)
    gap[1:] = (idx.to_series().diff().to_numpy()[1:] > np.timedelta64(24, "h"))
    first_monday = np.zeros(len(idx), dtype=bool)
    first_monday[1:] = (dow[1:] == 0) & (dow[:-1] != 0)
    return np.flatnonzero(first_monday | gap)


@dataclass
class World:
    """What a scenario hands the replay: the bars the family DECIDES on, the bars it is FILLED
    against (the same object unless the scenario is about latency), the spread multiplier for the
    cost model, the share of entries that fill at half size, and how much of the tape the
    transform actually touched. `applied == 0` means the scenario could not run here."""
    signal_bars: pd.DataFrame
    exec_bars: pd.DataFrame
    cost_mult: float = 1.0
    partial: float = 0.0
    applied: int = 0
    why: str = ""


def _s_usd_shock(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    n = len(bars)
    rng = _rng(seed, "usd_shock_liquidity_crash", name)
    if n < MIN_BARS:
        return World(bars, bars, why=f"{n} bars < {MIN_BARS}")
    i0 = int(rng.integers(200, n - 40))
    r = _logret(bars)
    r[i0:i0 + 4] += math.log1p(_usd_sign(sym) * 0.03) / 4.0
    out = _from_returns(bars, r)
    _scale_col(out, "spread", i0, min(n, i0 + 24), 4.0)
    _scale_col(out, "tick_volume", i0, min(n, i0 + 24), 0.5)
    _scale_col(out, "real_volume", i0, min(n, i0 + 24), 0.5)
    return World(out, out, cost_mult=4.0, applied=4)


def _s_spread_x5(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    out = bars.copy()
    _scale_col(out, "spread", 0, len(out), 5.0)
    return World(out, out, cost_mult=5.0, applied=len(out))


def _s_correlated(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    r = _logret(bars)
    sd = float(np.std(r[1:])) if len(r) > 2 else 0.0
    if len(bars) < MIN_BARS or sd <= 0.0:
        return World(bars, bars, why="no dispersion to replace" if sd <= 0 else "too few bars")
    out = _from_returns(bars, sd * _common_shock(bars.index, seed) + 0.2 * r)
    return World(out, out, applied=len(bars) - 1)


def _s_trend_break(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    n = len(bars)
    if n < MIN_BARS:
        return World(bars, bars, why=f"{n} bars < {MIN_BARS}")
    rng = _rng(seed, "instant_trend_break", name)
    b = int(rng.integers(120, n - 60))
    r = _logret(bars)
    mu = float(np.mean(r[b - 60:b]))
    if abs(mu) < 1e-12:
        return World(bars, bars, why="the 60 bars before the break carry no trend to flip")
    r[b:] -= 2.0 * mu
    out = _from_returns(bars, r)
    return World(out, out, applied=n - b)


def _s_cb_surprise(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    n = len(bars)
    r = _logret(bars)
    sigma = float(np.std(r[1:])) if len(r) > 2 else 0.0
    if n < MIN_BARS or sigma <= 0.0:
        return World(bars, bars, why="no dispersion to scale the surprise by" if n >= MIN_BARS
                     else f"{n} bars < {MIN_BARS}")
    idx = pd.DatetimeIndex(bars.index)
    hour = idx.hour.to_numpy()
    day = idx.normalize().to_numpy()
    at_hour = np.flatnonzero((hour == 14) & (np.arange(n) < n - 10))
    if at_hour.size == 0:
        return World(bars, bars, why="the calendar hour (14:00) never appears on this chart")
    seen: dict[Any, int] = {}
    for p in at_hour:                       # the FIRST bar of that hour on each day, once
        seen.setdefault(day[p], int(p))
    firsts = np.array(sorted(seen.values()), dtype="int64")
    rng = _rng(seed, "central_bank_surprise", name)
    take = min(8, firsts.size)
    events = np.sort(rng.choice(firsts, size=take, replace=False))
    signs = rng.choice(np.array([-1.0, 1.0]), size=take)
    r[events] += signs * 2.5 * sigma
    out = _from_returns(bars, r)
    for p in events:
        _scale_col(out, "spread", int(p), min(n, int(p) + 6), 3.0)
    return World(out, out, applied=int(take))


def _s_vol_doubling(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    n = len(bars)
    if n < MIN_BARS:
        return World(bars, bars, why=f"{n} bars < {MIN_BARS}")
    r = _logret(bars)
    mu = pd.Series(r).rolling(20, min_periods=1).mean().to_numpy()
    out = _from_returns(bars, mu + 2.0 * (r - mu))
    return World(out, out, applied=n - 1)


def _s_weekend_gap(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    pos = _monday_opens(bars.index)
    if pos.size == 0:
        return World(bars, bars, why="no Monday open (or weekly break) in the sample")
    rng = _rng(seed, "weekend_gap", name)
    r = _logret(bars)
    r[pos] += np.log1p(rng.choice(np.array([-0.015, 0.015]), size=pos.size))
    out = _from_returns(bars, r)
    return World(out, out, applied=int(pos.size))


def _s_weekend_gap_removed(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    """The INVERSE of `weekend_gap`, and the one `needs_weekend_gap` reads: flatten the gap the
    tape really has, so the Monday open prints at Friday's close."""
    pos = _monday_opens(bars.index)
    if pos.size == 0:
        return World(bars, bars, why="no Monday open (or weekly break) in the sample")
    o = np.asarray(bars["open"], dtype="float64")
    c = np.asarray(bars["close"], dtype="float64")
    gap = np.log(np.maximum(o[pos], 1e-12)) - np.log(np.maximum(c[pos - 1], 1e-12))
    gap = np.nan_to_num(gap, nan=0.0, posinf=0.0, neginf=0.0)
    live = int(np.count_nonzero(np.abs(gap) > 1e-12))
    if live == 0:
        return World(bars, bars, why="every Monday open already prints at the previous close")
    r = _logret(bars)
    r[pos] -= gap
    out = _from_returns(bars, r)
    return World(out, out, applied=live)


def _s_feed_latency(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    """The signal bars stay; the EXECUTABLE prices are the next bar's. An edge that only exists
    because the fill landed on precisely the bar the clock assumed dies here and nowhere else."""
    if len(bars) < 3:
        return World(bars, bars, why="too few bars to shift")
    return World(bars.iloc[:-1], bars.shift(-1).iloc[:-1], applied=len(bars) - 1)


def _s_partial_fills(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    return World(bars, bars, partial=0.3, applied=len(bars))


def _s_missing(bars: pd.DataFrame, sym: str, seed: int, name: str) -> World:
    n = len(bars)
    if n < MIN_BARS:
        return World(bars, bars, why=f"{n} bars < {MIN_BARS}")
    rng = _rng(seed, "missing_releases", name)
    blocks = max(1, round(0.10 * n / 6.0))
    starts = rng.choice(n - 6, size=min(blocks, n - 6), replace=False)
    keep = np.ones(n, dtype=bool)
    for s in starts:
        keep[int(s):int(s) + 6] = False
    dropped = int(n - keep.sum())
    if dropped == 0 or keep.sum() < 50:
        return World(bars, bars, why="dropping the blocks would leave too little tape")
    out = bars.loc[keep]
    return World(out, out, applied=dropped)


#: Name -> (what it does, the transform). Order is the order they run and the order they print.
SCENARIOS: dict[str, tuple[str, Any]] = {
    "usd_shock_liquidity_crash": (
        "-3% dollar-basket move over 4 bars (signed by the instrument's dollar leg, half for a "
        "cross with none), spread column x4 and volume halved for 24 bars, round trip charged "
        "x4 across the replay because the engine's cost model is one constant",
        _s_usd_shock),
    "spread_x5": ("round trip charged at 5x the registry spread; the spread column widened too",
                  _s_spread_x5),
    "correlations_to_one": ("every instrument's return replaced by one common timestamp-keyed "
                            "shock at its own volatility, plus 20% of its own return",
                            _s_correlated),
    "instant_trend_break": ("the mean 60-bar drift before one random bar is subtracted twice "
                            "from every bar after it -- the prevailing trend, sign-flipped",
                            _s_trend_break),
    "central_bank_surprise": ("up to 8 events at the 14:00 bar, each a +/-2.5 sigma close-to-close "
                              "jump with the spread column x3 for the following 6 bars",
                              _s_cb_surprise),
    "vol_doubling": ("returns scaled x2 around their own 20-bar rolling mean", _s_vol_doubling),
    "weekend_gap": ("a +/-1.5% gap inserted at every Monday open (or weekly break)",
                    _s_weekend_gap),
    "weekend_gap_removed": ("the inverse: every Monday gap flattened onto the previous close",
                            _s_weekend_gap_removed),
    "feed_latency": ("executable prices shifted one bar forward against the signal bars",
                     _s_feed_latency),
    "partial_fills": ("30% of entries fill at half size -- R scaled, never dropped",
                      _s_partial_fills),
    "missing_releases": ("10% of bars removed in blocks of six", _s_missing),
}


# ---------------------------------------------------------------- the replay

def family_fn(family: str) -> Any:
    """The family constructor, from the two registries the gauntlet reads and in its order.

    Kept as a module function so a test can hand this organ a family with a planted edge without
    touching either registry -- and so there is exactly ONE place that answers "can this desk
    still call the thing it certified".
    """
    fn = None
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{family}", None)
    except ImportError:
        fn = None
    if fn is None:
        try:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        except (ImportError, AttributeError):
            fn = None
    return fn


def _engine() -> Any:
    """(run_backtest, Costs) or None -- the certificate path's own replay when it is reachable."""
    try:
        from mt5desk.engine import Costs, run_backtest
    except ImportError:
        return None
    return run_backtest, Costs


def _per_unit_cost(meta: dict, mult: float) -> float:
    """`Costs.from_symbol`'s round trip, in price units -- the fallback's only cost arithmetic."""
    cs = float(meta.get("contract_size", 1e5) or 1e5)
    ts = float(meta.get("tick_size", 0.0) or 0.0)
    tv = float(meta.get("tick_value", 0.0) or 0.0)
    spread = max(float(meta.get("median_spread_pts", 0.0) or 0.0) * ts * cs * mult, 0.05)
    qpa = (cs * ts / tv) if (tv > 0 and cs > 0 and ts > 0) else 1.0
    return (spread + 2.25 * 2.0 * qpa) / cs


def _minimal_replay(df: pd.DataFrame, sigs: list, cost_px: float) -> list[float]:
    """Next-open entry, intrabar stop before target, TTL exit at the open. The fallback only.

    It deliberately does NOT model resting triggers, banking, trailing or pyramiding: half-copying
    the engine is how two replays of one rule drift apart. A row replayed here says so in `basis`.
    """
    o = np.asarray(df["open"], dtype="float64")
    h = np.asarray(df["high"], dtype="float64")
    lo_ = np.asarray(df["low"], dtype="float64")
    idx = pd.DatetimeIndex(df.index)
    idx_ns = np.asarray(idx.as_unit("ns").asi8, dtype="int64")
    out: list[float] = []
    last_exit = -1
    for sig in sigs:
        i = int(np.searchsorted(idx_ns, pd.Timestamp(sig.time).value)) + 1
        if i <= 0 or i >= len(idx) - 1 or i <= last_exit:
            continue
        entry, side = float(o[i]), int(sig.side)
        sd = abs(entry - float(sig.stop))
        if not (entry > 0) or sd <= 0:
            continue
        ttl = max(1, int(getattr(sig, "ttl_bars", 1) or 1))
        exit_px, held = None, 0
        for j in range(i, min(len(idx), i + ttl)):
            held = j - i + 1
            if side > 0 and lo_[j] <= float(sig.stop):
                exit_px = float(sig.stop)
            elif side > 0 and h[j] >= float(sig.target):
                exit_px = float(sig.target)
            elif side < 0 and h[j] >= float(sig.stop):
                exit_px = float(sig.stop)
            elif side < 0 and lo_[j] <= float(sig.target):
                exit_px = float(sig.target)
            if exit_px is not None:
                break
        if exit_px is None:
            k = min(i + ttl, len(idx) - 1)
            exit_px, held = float(o[k]), k - i + 1
        last_exit = i + held - 1
        out.append((exit_px - entry) / sd * side - cost_px / sd)
    return out


def _signals(fn: Any, bars: pd.DataFrame, side: int, params: dict, selector: str) -> list:
    """The desk's ONE call shape (`mt5desk.family_call.signals`), session filter included."""
    from mt5desk.family_call import signals as call
    p = dict(params)
    if selector:
        p["session"] = selector
    return list(call(fn, bars, side=side, params=p))


def _metrics(rs: list[float]) -> dict[str, float]:
    n = len(rs)
    if n == 0:
        return {"n": 0, "expectancy": 0.0, "t": 0.0, "max_dd_r": 0.0}
    a = np.asarray(rs, dtype="float64")
    m = float(a.mean())
    sd = float(a.std(ddof=1)) if n > 1 else 0.0
    t = m / (sd / math.sqrt(n)) if (n > 1 and sd > 0) else 0.0
    eq = np.cumsum(a)
    return {"n": n, "expectancy": round(m, 6), "t": round(t, 3),
            "max_dd_r": round(float(np.max(np.maximum.accumulate(eq) - eq)), 4)}


def _halve(rs: list[float], share: float, seed: int, name: str) -> tuple[list[float], int]:
    """`partial_fills`: a deterministic `share` of entries filled at half size -> R halved."""
    if not rs or share <= 0:
        return rs, 0
    rng = _rng(seed, "partial_fills", name)
    hit = rng.random(len(rs)) < share
    return [r * 0.5 if k else r for r, k in zip(rs, hit, strict=True)], int(hit.sum())


# ---------------------------------------------------------------- what gets broken

@dataclass(frozen=True)
class Sleeve:
    name: str
    lane: str
    symbol: str
    family: str
    timeframe: str
    side: int
    selector: str
    params: dict[str, Any] = field(default_factory=dict)


def _side(value: Any) -> int:
    return -1 if str(value or "").strip().upper() in {"SHORT", "-1"} else 1


def _timeframe(row: dict, params: dict) -> str:
    try:
        from research.frontier_identity import timeframe_of
        return timeframe_of({"timeframe": row.get("timeframe"), "params": params})
    except ImportError:
        return str(row.get("timeframe") or params.get("timeframe") or "H1").upper()


def _cert_spec(survivors: dict, row: dict) -> dict:
    """A live sleeve's parameters, which the sleeve row does NOT carry.

    A promoted row names its CERTIFICATE (`certificate.cell`), not its parameterisation -- so
    `discovered` arrives here with no `feature`, `band` or `horizon` at all. Replaying it on the
    row alone is replaying a different rule, and it fails silently in the most misleading way
    available: the family emits nothing and the sleeve reads as "produces no trades". Measured on
    this box 2026-09-16: 53 of the 66 registered sleeves name a cell that resolves exactly into
    `UNIVERSAL_SURVIVORS.json`, which is where their parameters have been all along.
    """
    cert = row.get("certificate")
    cell = str(cert.get("cell") or "") if isinstance(cert, dict) else ""
    if not cell:
        return {}
    for key, entry in survivors.items():
        if key == cell or key.endswith(cell):
            return dict((entry or {}).get("shadow_spec") or {})
    return {}


def load_sleeves() -> tuple[list[Sleeve], list[dict[str, Any]]]:
    """Every certified cell and every registered sleeve -- and, separately, the rows that cannot
    be turned into something replayable, which are UNMEASURED and named rather than dropped."""
    out: list[Sleeve] = []
    gaps: list[dict[str, Any]] = []
    survivors = (_read_json(SURVIVORS) or {}).get("survivors") or {}
    for key, row in survivors.items():
        spec = (row or {}).get("shadow_spec") or {}
        params = dict(spec.get("params") or {})
        sym, fam = str(spec.get("symbol") or ""), str(spec.get("family") or "")
        if not sym or not fam:
            gaps.append({"name": key, "lane": "certified",
                         "why": "no symbol/family on shadow_spec"})
            continue
        out.append(Sleeve(key, "certified", sym, fam, _timeframe(spec, params),
                          _side(spec.get("side")), str(spec.get("selector") or ""), params))
    doc = _read_json(SLEEVES) or {}
    for row in (doc.get("sleeves") or []):
        name = str(row.get("name") or "")
        sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "")
        if not sym or not fam:
            gaps.append({"name": name, "lane": "live", "symbol": sym,
                         "why": "sleeve row names no registry family (the gold windows carry "
                                "their rule in the gateway)"})
            continue
        spec = _cert_spec(survivors, row)
        params = dict(row.get("params") or spec.get("params") or {})
        out.append(Sleeve(name, "live", sym, fam, _timeframe(row, params),
                          _side(row.get("side") or spec.get("side")),
                          str(row.get("session") or row.get("selector")
                              or spec.get("selector") or ""), params))
    return out, gaps


def rotate(sleeves: list[Sleeve], state: dict, limit: int) -> list[Sleeve]:
    """Least-recently-tested first, name as the tie-break so the order is the same on both boxes."""
    tested = state.get("tested") or {}
    return sorted(sleeves, key=lambda s: (str(tested.get(s.name) or ""), s.name))[:max(0, limit)]


# ---------------------------------------------------------------- the pass

def probe_sleeve(sleeve: Sleeve, meta: dict, seed: int, basis: str,
                 budget_s: float = BUDGET_S) -> dict[str, Any]:
    """One sleeve through every world. Returns a result row, or a row carrying `unmeasured`."""
    started = time.monotonic()
    path = UNIVERSE / f"{sleeve.symbol}_{sleeve.timeframe}.parquet"
    if not path.exists():
        return {"unmeasured": f"no bars at {path.name}"}
    try:
        bars = pd.read_parquet(path)
    except (OSError, ValueError) as exc:
        return {"unmeasured": f"{path.name} unreadable: {type(exc).__name__}"}
    if len(bars) < MIN_BARS:
        return {"unmeasured": f"{len(bars)} bars on {path.name} < {MIN_BARS}"}
    fn = family_fn(sleeve.family)
    if fn is None:
        return {"unmeasured": f"family {sleeve.family!r} is in neither registry"}
    try:
        from mt5desk.family_inputs import resolve, strip_identity_keys
        extra, why = resolve(sleeve.symbol, sleeve.family, sleeve.params, bars)
        if extra is None:
            return {"unmeasured": f"inputs unresolvable: {why}"}
        params = {**strip_identity_keys(sleeve.family, sleeve.params), **extra}
    except ImportError as exc:
        return {"unmeasured": f"family_inputs unavailable: {exc}"}

    eng = _engine() if basis != "minimal_replay" else None
    use = "engine" if eng is not None else "minimal_replay"
    sym_meta = dict(meta.get(sleeve.symbol) or {})

    def replay(world: World) -> list[float] | str:
        try:
            sigs = _signals(fn, world.signal_bars, sleeve.side, params, sleeve.selector)
        except Exception as exc:                      # a family that raises is a gap, not a zero
            return f"family raised: {type(exc).__name__}: {str(exc)[:70]}"
        if not sigs:
            return []
        try:
            if eng is not None:
                run_backtest, costs_cls = eng
                costs = costs_cls.from_symbol(sym_meta, mult=world.cost_mult)
                res = run_backtest(world.exec_bars, sigs, costs)
                return [float(t.r_multiple) for t in res.trades]
            return _minimal_replay(world.exec_bars, sigs,
                                   _per_unit_cost(sym_meta, world.cost_mult))
        except Exception as exc:
            return f"replay raised: {type(exc).__name__}: {str(exc)[:70]}"

    base = replay(World(bars, bars, applied=len(bars)))
    if isinstance(base, str):
        return {"unmeasured": base}
    if not base:
        return {"unmeasured": "the untouched tape produces no trades; nothing to break"}
    baseline = _metrics(base)

    rows: dict[str, Any] = {}
    for scenario, (_what, build) in SCENARIOS.items():
        if time.monotonic() - started > budget_s:
            rows[scenario] = {"status": "UNMEASURED",
                              "why": f"per-sleeve budget {budget_s:g}s exhausted"}
            continue
        try:
            world = build(bars, sleeve.symbol, seed, sleeve.name)
        except Exception as exc:
            rows[scenario] = {"status": "UNMEASURED",
                              "why": f"transform raised: {type(exc).__name__}"}
            continue
        if world.applied <= 0:
            rows[scenario] = {"status": "UNMEASURED",
                              "why": world.why or "the transform touched no bar"}
            continue
        rs = replay(world)
        if isinstance(rs, str):
            rows[scenario] = {"status": "UNMEASURED", "why": rs}
            continue
        halved = 0
        if world.partial > 0:
            rs, halved = _halve(rs, world.partial, seed, sleeve.name)
        row = {"status": "MEASURED", "applied": int(halved or world.applied), **_metrics(rs)}
        row["delta_expectancy"] = round(row["expectancy"] - baseline["expectancy"], 6)
        rows[scenario] = row

    flags = flags_for(baseline, rows)
    measured = {k: v for k, v in rows.items() if v.get("status") == "MEASURED"}
    worst = min(measured.items(), key=lambda kv: kv[1]["expectancy"], default=None)
    return {
        "name": sleeve.name, "lane": sleeve.lane, "symbol": sleeve.symbol,
        "family": sleeve.family, "timeframe": sleeve.timeframe, "side": sleeve.side,
        "selector": sleeve.selector, "basis": use, "baseline": baseline,
        "scenarios": rows, "flags": flags,
        "worst_scenario": ({"name": worst[0], "expectancy": worst[1]["expectancy"]}
                           if worst else None),
        "verdict": ("STRUCTURAL_FAILURE" if flags
                    else "NO_BASELINE_EDGE" if baseline["expectancy"] <= 0
                    else "NO_NAMED_FAILURE"),
        "elapsed_s": round(time.monotonic() - started, 2),
    }


def flags_for(baseline: dict[str, float], rows: dict[str, Any]) -> list[str]:
    """The named failure modes this sleeve showed. Never a merit: every rule points one way.

    A scenario in which the family STOPS SIGNALLING scores n=0, expectancy 0.0 and therefore
    flags. That is the intended reading, not an artefact of the arithmetic: a sleeve whose rule
    only fires when the tape has the property the scenario removed exists BECAUSE of that
    property, which is precisely the structural dependency this organ was built to name. The row
    carries `n` so the reader sees which of the two shapes the flag came from.
    """
    base = float(baseline.get("expectancy") or 0.0)
    if base <= 0:                        # nothing to fall from; see `verdict` NO_BASELINE_EDGE
        return []
    out = []
    for flag, (scenario, test) in FLAG_RULES.items():
        row = rows.get(scenario) or {}
        if row.get("status") != "MEASURED":
            continue                     # an unrun transform never produces a clean verdict
        exp = float(row.get("expectancy") or 0.0)
        if (test == "sign" and exp < 0) or (test == "half" and exp < 0.5 * base):
            out.append(flag)
    return sorted(out)


def run(max_sleeves: int = MAX_SLEEVES, seed: int = 0, basis: str = "auto",
        budget_s: float = BUDGET_S) -> dict[str, Any]:
    sleeves, gaps = load_sleeves()
    state = _read_json(STATE) or {}
    picked = rotate(sleeves, state, max_sleeves)
    meta = _read_json(UNIVERSE / "universe.json") or {}
    results: list[dict[str, Any]] = []
    unmeasured: list[dict[str, Any]] = list(gaps)
    tested = dict(state.get("tested") or {})
    at = _now()
    for sleeve in picked:
        try:
            row = probe_sleeve(sleeve, meta, seed, basis, budget_s)
        except Exception as exc:          # one bad sleeve never costs the batch its other rows
            row = {"unmeasured": f"probe raised: {type(exc).__name__}: {str(exc)[:70]}"}
        tested[sleeve.name] = at          # stamped on ATTEMPT: an unmeasurable sleeve cannot pin
        if "unmeasured" in row:           # the queue against everything behind it
            unmeasured.append({"name": sleeve.name, "lane": sleeve.lane, "symbol": sleeve.symbol,
                               "family": sleeve.family, "why": row["unmeasured"]})
            continue
        results.append(row)
    summary: dict[str, int] = {}
    for row in results:
        for flag in row["flags"]:
            summary[flag] = summary.get(flag, 0) + 1
    return {
        "at": at, "seed": int(seed), "basis": basis,
        "scenarios": [{"name": k, "what": v[0]} for k, v in SCENARIOS.items()],
        "flag_rules": {k: {"scenario": s, "test": t} for k, (s, t) in FLAG_RULES.items()},
        "n_candidates": len(sleeves), "n_sleeves": len(results),
        "results": results,
        "flags_summary": dict(sorted(summary.items())),
        "unmeasured": unmeasured,
        "state": {"tested": tested, "updated_at": at},
        "rule": RULE,
    }


def _print(report: dict[str, Any]) -> None:
    print(f"SYNTHETIC REGIMES  {report['n_sleeves']} sleeve(s) of {report['n_candidates']} "
          f"through {len(SCENARIOS)} worlds, seed {report['seed']}")
    print(f"  {'sleeve':38s} {'lane':9s} {'base E[R]':>9s} {'worst':>9s}  worst world / flags")
    for row in report["results"]:
        worst = row.get("worst_scenario") or {}
        print(f"  {row['name'][:38]:38s} {row['lane']:9s} "
              f"{row['baseline']['expectancy']:9.4f} {float(worst.get('expectancy', 0.0)):9.4f}  "
              f"{str(worst.get('name', '-'))[:22]:22s} "
              f"{','.join(row['flags']) or row['verdict']}")
    if report["flags_summary"]:
        print("  STRUCTURAL FAILURES: "
              + ", ".join(f"{k}={v}" for k, v in report["flags_summary"].items()))
    else:
        print("  no named failure mode in this batch (which is not a merit -- see `rule`)")
    print(f"  unmeasured: {len(report['unmeasured'])}")
    for row in report["unmeasured"][:6]:
        print(f"    {str(row.get('name'))[:44]:44s} {str(row.get('why'))[:60]}")
    print(f"  rule: {RULE}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="adversarial synthetic regimes for every sleeve")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--max-sleeves", type=int, default=MAX_SLEEVES,
                    help="least-recently-tested first (default 25)")
    ap.add_argument("--seed", type=int, default=0, help="the worlds are a function of this")
    ap.add_argument("--basis", choices=("auto", "engine", "minimal_replay"), default="auto",
                    help="'minimal_replay' forces the fallback replay; 'auto' prefers the engine")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S, help="wall budget per sleeve")
    a = ap.parse_args(argv)
    report = run(a.max_sleeves, a.seed, a.basis, a.budget_s)
    _print(report)
    if a.dry_run:
        print("  dry run: nothing written")
        return 0
    _atomic_json(REPORT, {k: v for k, v in report.items() if k != "state"})
    _atomic_json(STATE, report["state"])
    print(f"  wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
