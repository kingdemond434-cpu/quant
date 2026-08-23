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
    return None if not paths else pd.read_parquet(paths[-1])


def build() -> dict:
    rows = []
    for direct, base_usd, quote_usd in TRIANGLES:
        frames = [_latest(symbol) for symbol in (direct, base_usd, quote_usd)]
        if any(frame is None for frame in frames):
            rows.append({"triangle": direct, "status": "UNMEASURED",
                         "why": "one or more synchronized Fusion tick legs are absent"})
            continue
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
