"""ONE ANSWER TO "WHAT ARE THIS SYMBOL'S LAST N TAPE DAYS", for every tape reader.

THE DEFECT THIS ENDS (found 2026-10-29). `data/tape/ticks/<SYM>/` holds two writers' files:

    2026-10-29.parquet  mt5desk/tape.record_ticks  ts, time_msc, bid, ask   (keyed by TICK day)
    20261029.parquet    moat/moat_silver.py         time_msc, bid, ask, recv (RECEIVE day)

Every reader took `sorted(d.glob("*.parquet"))[-30:]` and read `columns=["ts", "bid", "ask"]`.
`-` (0x2D) sorts before `0` (0x30), so every compact name sorts AFTER every dashed name and the
"last 30 days" were the last 30 COMPACT files -- each of which has no `ts`, so each read threw,
each `except: continue` swallowed it, and `_tape_series` returned (None, None) for every symbol
while the recorder wrote 138 live symbols an hour. 66k liquidity_regime / orderflow_imbalance
cells were minted against a tape their judge could not open, and zero were ever judged.

THE RULES, so no reader grows its own opinion again:
  * A file's DAY comes from its name, in either convention; an undateable name is not tape.
  * Days are ordered as DATES, never as strings.
  * A shared day is the UNION of both writers, deduplicated on (time_msc, bid, ask) -- the
    recorder's own contract (moat_recorder.py: "the reader dedupes"). Picking one file per day
    loses ticks: after a restart one writer holds the morning and the other the evening, and the
    two key a day differently (tick day vs receive day), so a compact file can hold the first
    minutes of the next day. Picking by size or by rows was measured to drop 36,000 of 86,400.
  * The window is the newest N day KEYS plus one neighbouring key either side (a receive-day file
    can hold the edge of the window), trimmed back to the window's own dates after the union.
  * `ts` is UTC, derived from `time_msc` when the file has none. Both writers stamp `time_msc`
    from the same terminal field, so the derived clock is the dashed writer's clock exactly.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

DEDUPE_KEY = ("time_msc", "bid", "ask")


def day_key(stem: str) -> str | None:
    """`2026-10-29` and `20261029` are one day written by two writers. Normalise, or None."""
    s = stem.replace("-", "")
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
    except ValueError:
        return None


def day_candidates(sym_dir: Path) -> dict[str, list[Path]]:
    """{YYYY-MM-DD: [every file holding that day key]} for one symbol directory. No file opened."""
    by_day: dict[str, list[Path]] = {}
    if not sym_dir.is_dir():
        return by_day
    for f in sym_dir.glob("*.parquet"):
        key = day_key(f.stem)
        if key is not None:
            by_day.setdefault(key, []).append(f)
    for files in by_day.values():
        files.sort(key=lambda p: p.name)
    return by_day


def _window(by_day: dict[str, list[Path]], last: int) -> tuple[list[str], list[Path]]:
    """(the newest `last` day keys, every file to read for them incl. one neighbour each side)."""
    keys = sorted(by_day)
    if last <= 0 or not keys:
        return [], []
    want = keys[-last:]
    lo = (date.fromisoformat(want[0]) - timedelta(days=1)).isoformat()
    files = [f for k in keys if k >= lo for f in by_day[k]]
    return want, files


def day_files(sym_dir: Path, last: int | None = None) -> list[Path]:
    """Every file (both writers) holding the newest `last` day keys, oldest key first."""
    by_day = day_candidates(sym_dir)
    keys = sorted(by_day)
    if last is not None:
        keys = keys[-last:] if last > 0 else []
    return [f for k in keys for f in by_day[k]]


def read_quotes(path: Path, extra: tuple[str, ...] = ()) -> pd.DataFrame | None:
    """`ts`, `time_msc`, `bid`, `ask` (+ any of `extra` the file holds) from either writer, or None.

    `ts` is UTC. A file with neither `ts` nor `time_msc`, or one that will not open, is None --
    the caller decides whether a missing file is fatal; this never guesses a clock.
    """
    import pandas as pd
    import pyarrow.parquet as pq
    try:
        names = set(pq.read_schema(path).names)  # type: ignore[no-untyped-call]
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
        # A ts-only legacy file: ms whatever unit the writer stored (tape.py stores ms, so a
        # bare int64 cast would read 1793282 where 1793282642940 is meant).
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df["time_msc"] = df["ts"].dt.as_unit("ms").astype("int64")
    return df


def union_frames(frames: list[pd.DataFrame]) -> pd.DataFrame | None:
    """Concat, drop rows without a quote or a clock, dedupe on (time_msc, bid, ask), sort by ts."""
    import pandas as pd
    if not frames:
        return None
    t = pd.concat(frames, ignore_index=True)
    t = t.dropna(subset=["ts", "time_msc", "bid", "ask"])
    t = t.drop_duplicates(subset=list(DEDUPE_KEY), keep="first")
    return t.sort_values("ts", kind="stable")


def recent_quotes(sym_dir: Path, last: int = 30, extra: tuple[str, ...] = ()
                  ) -> pd.DataFrame | None:
    """The newest `last` tape days, both writers unioned, as one frame indexed by UTC `ts`."""
    import pandas as pd
    want, files = _window(day_candidates(sym_dir), last)
    frames = [got for f in files if (got := read_quotes(f, extra)) is not None]
    t = union_frames(frames)
    if t is None:
        return None
    t = t[t["ts"] >= pd.Timestamp(want[0], tz="UTC")]
    return None if t.empty else t.set_index("ts")


def day_quotes(sym_dir: Path, day: str, extra: tuple[str, ...] = ()) -> pd.DataFrame | None:
    """One UTC day's ticks from both writers (and their neighbouring keys), ts as a COLUMN."""
    import pandas as pd
    by_day = day_candidates(sym_dir)
    d = date.fromisoformat(day)
    keys = [(d + timedelta(days=k)).isoformat() for k in (-1, 0, 1)]
    files = [f for k in keys for f in by_day.get(k, [])]
    t = union_frames([got for f in files if (got := read_quotes(f, extra)) is not None])
    if t is None:
        return None
    lo = pd.Timestamp(day, tz="UTC")
    t = t[(t["ts"] >= lo) & (t["ts"] < lo + pd.Timedelta(days=1))]
    return None if t.empty else t.reset_index(drop=True)
