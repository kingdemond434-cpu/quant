"""EXOGENOUS CONDITIONER -- an MT5 instrument conditioned on a data pack's own published series.

WHY THIS FILE EXISTS, AND IT IS A DEFECT REPORT (measured on the trading box 2026-09-24).
`desks/mt5/research/pack_cells.py` has been minting cells under the family name
`exogenous_conditioner` -- 432 of them in the canonical registry, each naming a lake series, a
column of it and a transform, each carrying a real falsifier. And the name did not exist:
`miner_candidate_compiler._registered_family` requires `family_<name>` in `mt5desk/families.py`
or membership of `families_orthogonal.ORTHOGONAL_FAMILIES`, and `exogenous_conditioner` was in
neither. Every one of those cells therefore exited `compile_row` as NEEDS_EXACT_RULE_EXTRACTION
and could never reach a docket, however well it scored. A producer minting under a name no
generator implements is a pipeline whose output nothing can execute.

THE MECHANISM, and it is not a price pattern. A data pack publishes a statistic -- a fixing, an
exchange's daily aggregate, a monetary authority's open API -- and the instruments that pack's
country trades are a different asset when that statistic is at an extreme than when it is at its
middle. The bet is on the EXOGENOUS INFORMATION, which is why the family refuses to run without
it: a conditioner with no series is not a momentum family, it is a family with nothing to say,
and it says nothing. That is the honest-limits contract `families_orthogonal` states for every
family in it.

THE POINT-IN-TIME JOIN IS THE PART THAT CAN GO WRONG SILENTLY, so it is stated here. The pack's
rows carry `available_time` -- genuinely UTC, written by the lake's own PIT envelope. The bar
index is BROKER time under a UTC tzinfo (+2 winter, +3 summer; see `libs/research/bar_clock`), so
a UTC series reindexed straight onto it lands two to three hours EARLY, which is lookahead. The
series is therefore lagged by `lag_hours` -- a full publication day by default -- BEFORE the
forward fill, so the three-hour clock offset cannot reach the bar it conditions. This is the same
property `family_macro_conditional` depends on; there it was a property of its producer, and here
it is enforced in the family itself because this family loads its own input.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

#: Where `asia_parser._canonicalise` lands a pack's canonical frame, under its bare id. Named
#: from this file's own location so a test tree and the box agree without an environment variable.
SERIES_DIR = Path(__file__).resolve().parents[1] / "data" / "lake" / "series"

#: The point-in-time envelope columns. They are the STAMP, never a signal -- `pack_cells` strips
#: the same set when it chooses which columns are conditioners, and the two must not disagree.
STAMP_COLUMNS: frozenset[str] = frozenset({
    "event_time", "published_time", "available_time", "revision_time", "retrieval_time",
    "ingested_time", "source_id", "vintage_id"})

#: The three shapes a conditioner may read a column in, exactly as `pack_cells.TRANSFORMS`
#: enumerates them. All three are price-free and computable from the series alone, so the gauntlet
#: judges the PACK's information rather than a modelling choice made here.
TRANSFORMS: tuple[str, ...] = ("level_z", "delta", "delta_z")

#: Hours the series is held back before it may condition a bar. A full publication day, so the
#: broker clock's two-to-three hour offset from UTC cannot produce a lookahead join.
DEFAULT_LAG_HOURS = 24

#: Bars of history the z-score is measured over, and the minimum non-null conditioner values
#: needed before the family will emit anything at all. Below it the reading is UNMEASURED.
DEFAULT_Z_WINDOW = 250
MIN_OBSERVATIONS = 30


def series_path(source: str, root: Path | None = None) -> Path | None:
    """The pack's canonical frame, or None. Absence is UNMEASURED and emits nothing."""
    base = root or SERIES_DIR
    for suffix in (".parquet", ".csv"):
        p = base / f"{source!s}{suffix}"
        if p.exists():
            return p
    return None


def _load(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception:
        return None


def conditioner(source: str, signal: str, transform: str, *, lag_hours: int = DEFAULT_LAG_HOURS,
                z_window: int = DEFAULT_Z_WINDOW, root: Path | None = None) -> pd.Series | None:
    """The pack's column as a lagged, transformed series on its own `available_time` clock.

    None whenever the pack, the column, the stamp or the transform is unavailable -- every one of
    which is UNMEASURED and none of which is a reason to fall back to price.
    """
    if not source or not signal or str(signal) in STAMP_COLUMNS:
        return None
    path = series_path(source, root)
    if path is None:
        return None
    df = _load(path)
    if df is None or df.empty or str(signal) not in df.columns:
        return None
    if "available_time" not in df.columns:
        return None          # no PIT stamp means no honest join; never guess one
    stamp = pd.to_datetime(df["available_time"], errors="coerce", utc=True)
    value = pd.to_numeric(df[str(signal)], errors="coerce")
    s = pd.Series(value.to_numpy(), index=stamp).dropna()
    s = s[s.index.notna()]
    if s.empty:
        return None
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    t = str(transform or "level_z")
    if t == "delta":
        s = s.diff()
    elif t == "delta_z":
        s = s.diff()
        t = "level_z"
    if t == "level_z":
        w = max(5, int(z_window))
        mu = s.rolling(w, min_periods=5).mean()
        sd = s.rolling(w, min_periods=5).std(ddof=0)
        s = (s - mu) / sd.replace(0.0, np.nan)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return None
    # THE LAG, BEFORE ANY ALIGNMENT. See the module docstring: the bar clock is broker time and
    # this series is UTC, so the offset is absorbed by holding the value back a publication day.
    return s.shift(freq=pd.Timedelta(hours=max(0, int(lag_hours))))


def family_exogenous_conditioner(
    df: pd.DataFrame,
    *,
    source: str = "",
    signal: str = "",
    transform: str = "level_z",
    threshold: float = 1.0,
    side_when_high: int = 1,
    lag_hours: int = DEFAULT_LAG_HOURS,
    z_window: int = DEFAULT_Z_WINDOW,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 96,
    series_root: Path | None = None,
) -> list[Signal]:
    """Take a directional stance while the pack's own published statistic is at an extreme.

    REFUSES -- returns no signals -- without the pack, the column, its point-in-time stamp or
    enough observations to measure. `delta` carries raw units, so its extreme is `threshold`
    interpreted directly; `level_z` and `delta_z` are standard deviations of the column's own
    history. Nothing here reads price except to size the stop and to place the order.
    """
    cond = conditioner(source, signal, transform, lag_hours=lag_hours, z_window=z_window,
                       root=series_root)
    if cond is None or len(cond) < MIN_OBSERVATIONS:
        return []
    d = _h1(df)
    if d.empty:
        return []
    try:
        m = cond.reindex(cond.index.union(d.index)).ffill().reindex(d.index)
    except (TypeError, ValueError):
        return []              # a series that will not align to the bar clock is UNMEASURED
    atr = _atr(d, atr_n)
    thr = abs(float(threshold))
    signals: list[Signal] = []
    for i in range(atr_n, len(d) - 1):
        mv = m.iloc[i]
        if mv is None or not np.isfinite(mv) or abs(float(mv)) < thr:
            continue
        side = side_when_high if float(mv) > 0 else -side_when_high
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(d["close"].iloc[i])
        signals.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl_bars,
                              tag="exogenous_conditioner", trigger=None, wait_bars=1))
    return signals
