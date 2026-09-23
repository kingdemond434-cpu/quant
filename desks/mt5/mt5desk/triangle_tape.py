"""Executable FX-triangle evidence from synchronized Fusion bid/ask ticks.

This measures quoted, spread-inclusive loops. It grants no promotion authority: latency, rejects
and multi-leg fill risk still require prospective shadow execution evidence.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
from mt5desk.tape import TICKS

OUT = TICKS.parent / "triangle_executable.json"
TRIANGLES = (
    ("EURGBP", "EURUSD", "GBPUSD"),
    ("AUDNZD", "AUDUSD", "NZDUSD"),
)
MAX_SKEW_MS = 250
#: The three columns a quote leg must carry. Checked by name before any arithmetic so a leg with
#: the wrong schema is reported as UNMEASURED against ITS OWN symbol, rather than raising out of
#: the hourly cycle where the message names no file.
QUOTE_COLUMNS = frozenset({"ts", "bid", "ask"})


def normalise(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a frame carrying `ts` as a COLUMN, whatever shape its parquet was written in.

    WHY THIS EXISTS. `tape.py` writes ticks with ``index=False`` and an explicit `ts` column, so
    the common case needs nothing. But the tape on the box has been written by more than one
    generation of this code, and a frame that went through an index-carrying writer reads back
    with `ts` as the INDEX and no such column. ``frame[["ts", "bid", "ask"]]`` then raises
    ``KeyError: "['ts'] not in index"`` -- measured on the box 2026-09-04 onward, every hour.

    That failure was worse than it looked. `record_tape` runs `tape.main` FIRST and it succeeded
    (359,107 ticks on the 09-06 run), so the desk went on collecting ticks hourly while the
    triangle evidence quietly stopped being produced and the leg returned an error dict nobody
    read. Recovering `ts` from the index costs nothing and is unambiguous: there is exactly one
    time axis in a tick frame.
    """
    if "ts" in frame.columns:
        return frame
    index = frame.index
    if index.name == "ts" or isinstance(index, pd.DatetimeIndex):
        out = frame.reset_index()
        return out if "ts" in out.columns else out.rename(columns={out.columns[0]: "ts"})
    return frame                      # genuinely absent -- build() names the file and its columns


def executable_loops(direct: pd.DataFrame, base_usd: pd.DataFrame,
                     quote_usd: pd.DataFrame, tolerance_ms: int = MAX_SKEW_MS) -> pd.DataFrame:
    """Align past/nearest quotes and return both USD-starting executable loop returns."""
    def clean(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        out = frame[["ts", "bid", "ask"]].copy().sort_values("ts")
        out = out[(out["bid"] > 0) & (out["ask"] >= out["bid"])]
        return out.rename(columns={"bid": f"{prefix}_bid", "ask": f"{prefix}_ask"})

    aligned = clean(direct, "d")
    tol = pd.Timedelta(milliseconds=tolerance_ms)
    for frame, prefix in ((base_usd, "b"), (quote_usd, "q")):
        aligned = pd.merge_asof(
            aligned, clean(frame, prefix), on="ts", direction="nearest", tolerance=tol)
    aligned = aligned.dropna()
    aligned["direct_sell_loop"] = (
        aligned["d_bid"] * aligned["q_bid"] / aligned["b_ask"] - 1.0)
    aligned["direct_buy_loop"] = (
        aligned["b_bid"] / (aligned["q_ask"] * aligned["d_ask"]) - 1.0)
    return aligned


def _latest(symbol: str) -> pd.DataFrame | None:
    paths = sorted((TICKS / symbol).glob("*.parquet"))
    return None if not paths else normalise(pd.read_parquet(paths[-1]))


def build() -> dict:
    rows = []
    for direct, base_usd, quote_usd in TRIANGLES:
        legs = {symbol: _latest(symbol) for symbol in (direct, base_usd, quote_usd)}
        absent = [symbol for symbol, frame in legs.items() if frame is None]
        if absent:
            # NAME THE LEG. "one or more" sends the reader to three directories to find out which.
            rows.append({"triangle": direct, "status": "UNMEASURED",
                         "why": f"no Fusion tick parquet for {', '.join(absent)}"})
            continue
        unusable = {symbol: sorted(frame.columns)                       # type: ignore[union-attr]
                    for symbol, frame in legs.items()
                    if not QUOTE_COLUMNS <= set(frame.columns)}         # type: ignore[union-attr]
        if unusable:
            # A LEG WITH THE WRONG SCHEMA IS UNMEASURED, NOT AN EXCEPTION. Raising here took the
            # whole `record_tape` leg of the hourly cycle down with it and the message named no
            # symbol and no file. This says which leg, and what it actually carried.
            rows.append({
                "triangle": direct, "status": "UNMEASURED",
                "why": "tick parquet lacks the quote columns this needs ("
                       + "; ".join(f"{s}: has {c}" for s, c in unusable.items())
                       + f"); required {sorted(QUOTE_COLUMNS)}",
            })
            continue
        frames = [legs[symbol] for symbol in (direct, base_usd, quote_usd)]
        loops = executable_loops(*frames)  # type: ignore[arg-type]
        if loops.empty:
            rows.append({"triangle": direct, "status": "UNMEASURED",
                         "why": f"no three-leg quotes align within {MAX_SKEW_MS}ms"})
            continue
        best_sell = float(loops["direct_sell_loop"].max())
        best_buy = float(loops["direct_buy_loop"].max())
        rows.append({
            "triangle": direct,
            "status": "MEASURED_QUOTES_ONLY",
            "aligned_quotes": len(loops),
            "positive_loops": int(((loops["direct_sell_loop"] > 0)
                                   | (loops["direct_buy_loop"] > 0)).sum()),
            "best_direct_sell_bps": round(best_sell * 1e4, 4),
            "best_direct_buy_bps": round(best_buy * 1e4, 4),
            "promotion_authority": False,
        })
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "max_quote_skew_ms": MAX_SKEW_MS,
        "rows": rows,
        "next_gate": "prospective atomicity/latency/fill shadow before any strategy test",
    }


def main() -> int:
    report = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
