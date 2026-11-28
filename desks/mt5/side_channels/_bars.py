"""Local bars for the local-computation miners: the hypothesis-lane H1 universe, close only.

Two miners (seasonality, correlations) read the same files. Reading the CLOSE COLUMN of the
`<SYM>_H1.parquet` files of hypothesis-lane symbols only is what keeps them inside the suite's
180 s budget: the old seasonality loop opened every parquet in the folder, M1 files included, and
was killed on every box run (19:45Z and 21:45Z, 2026-11-13). Share CFDs are left out by the
two-lane order (`research.universe_policy`); they belong to the event lane.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parent.parent
UNIVERSE = DESK / "data" / "universe"
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.append(_p)


def hypothesis_symbols(universe: Path | None = None) -> list[str]:
    """Symbols with an H1 file whose lane is HYPOTHESIS, sorted."""
    try:
        import universe_policy as up
    except Exception:
        return []
    out = []
    for f in sorted((universe or UNIVERSE).glob("*_H1.parquet")):
        sym = f.name[: -len("_H1.parquet")]
        try:
            if up.lane(sym) == up.HYPOTHESIS:
                out.append(sym)
        except Exception:
            continue
    return out


def daily_close(sym: str, universe: Path | None = None) -> pd.Series | None:
    """Last H1 close of each UTC day, or None when the file is absent or unreadable."""
    f = (universe or UNIVERSE) / f"{sym}_H1.parquet"
    try:
        df = pd.read_parquet(f, columns=["close"])
    except Exception:
        return None
    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex):
        return None
    if idx.tz is None:
        df.index = idx.tz_localize("UTC")
    s = df["close"].astype("float64")
    s = s[s > 0].resample("1D").last().dropna()
    return s if len(s) else None
