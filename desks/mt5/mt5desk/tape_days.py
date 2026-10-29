"""ONE ANSWER TO "WHICH FILES ARE THIS SYMBOL'S LAST N TAPE DAYS", for every tape reader.

THE DEFECT THIS ENDS (found 2026-10-29). `data/tape/ticks/<SYM>/` holds two writers' files:

    2026-10-29.parquet   mt5desk/tape.record_ticks   ts, time_msc, bid, ask, ...
    20261029.parquet     moat/moat_silver.py          time_msc, bid, ask, recv_utc, ... NO `ts`

Every reader took `sorted(d.glob("*.parquet"))[-30:]` and read `columns=["ts", "bid", "ask"]`.
`-` (0x2D) sorts before `0` (0x30), so every compact name sorts AFTER every dashed name and the
"last 30 days" were the last 30 COMPACT files -- each of which has no `ts`, so each read threw,
each `except: continue` swallowed it, and `_tape_series` returned (None, None) for every symbol
while the recorder wrote 138 live symbols an hour. 66k liquidity_regime / orderflow_imbalance
cells were minted against a tape their judge could not open, and zero were ever judged.

THE RULES, so no reader grows its own opinion again:
  * A file's DAY comes from its name, in either convention; an undateable name is not tape.
  * Days are ordered as DATES, never as strings.
  * Where both writers hold the same day, the one with MORE ROWS wins (parquet footer, no read).
    Not the larger file: the silver carries string columns that make a thinner day heavier.
  * `ts` is derived from `time_msc` when the file has none. Both writers stamp `time_msc` from
    the same terminal field, so the derived clock is the dashed writer's clock exactly.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def day_key(stem: str) -> str | None:
    """`2026-10-29` and `20261029` are one day written by two writers. Normalise, or None."""
    s = stem.replace("-", "")
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
    except ValueError:
        return None


def _rows(path: Path) -> int:
    import pyarrow.parquet as pq
    try:
        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:  # a torn footer ranks last, it does not take the day down
        return -1


def day_candidates(sym_dir: Path) -> dict[str, list[Path]]:
    """{YYYY-MM-DD: [path, ...]} best first (most rows), for one symbol directory."""
    by_day: dict[str, list[Path]] = {}
    if not sym_dir.is_dir():
        return by_day
    for f in sym_dir.glob("*.parquet"):
        key = day_key(f.stem)
        if key is not None:
            by_day.setdefault(key, []).append(f)
    for files in by_day.values():
        if len(files) > 1:
            files.sort(key=_rows, reverse=True)
    return by_day


def day_files(sym_dir: Path, last: int | None = None) -> list[Path]:
    """One file per day, oldest -> newest by DATE, the newest `last` days when given."""
    by_day = day_candidates(sym_dir)
    keys = sorted(by_day)
    if last is not None:
        keys = keys[-last:] if last > 0 else []
    return [by_day[k][0] for k in keys]


def read_quotes(path: Path, extra: tuple[str, ...] = ()) -> pd.DataFrame | None:
    """`ts`, `time_msc`, `bid`, `ask` (+ any of `extra` the file holds) from either writer, or None.

    `ts` is UTC. A file with neither `ts` nor `time_msc`, or one that will not open, is None --
    the caller decides whether a missing day is fatal; this never guesses a clock.
    """
    import pandas as pd
    import pyarrow.parquet as pq
    try:
        names = set(pq.read_schema(path).names)
    except Exception:
        return None
    if not {"bid", "ask"} <= names or not ({"ts", "time_msc"} & names):
        return None
    cols = [c for c in ("ts", "time_msc", "bid", "ask", *extra) if c in names]
    try:
        df = pd.read_parquet(path, columns=list(dict.fromkeys(cols)))
    except Exception:
        return None
    if "time_msc" in df.columns:
        ms = pd.to_numeric(df["time_msc"], errors="coerce")
        derived = pd.to_datetime(ms, unit="ms", utc=True)
        df["ts"] = derived if "ts" not in df.columns else (
            pd.to_datetime(df["ts"], utc=True).fillna(derived))
    else:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df["time_msc"] = df["ts"].astype("int64") // 1_000_000
    return df


def read_day(sym_dir: Path, day: str, extra: tuple[str, ...] = ()) -> pd.DataFrame | None:
    """The best readable file for one day; falls back to the other writer when the best is torn."""
    for f in day_candidates(sym_dir).get(day, []):
        got = read_quotes(f, extra)
        if got is not None:
            return got
    return None


def recent_quotes(sym_dir: Path, last: int = 30, extra: tuple[str, ...] = ()
                  ) -> pd.DataFrame | None:
    """The newest `last` tape days as one frame indexed by UTC `ts`, quotes only, or None."""
    import pandas as pd
    by_day = day_candidates(sym_dir)
    frames = []
    for key in sorted(by_day)[-last:] if last > 0 else []:
        for f in by_day[key]:
            got = read_quotes(f, extra)
            if got is not None:
                frames.append(got)
                break
    if not frames:
        return None
    t = pd.concat(frames, ignore_index=True)
    t = t.dropna(subset=["ts", "bid", "ask"]).sort_values("ts", kind="stable")
    return t.set_index("ts")
