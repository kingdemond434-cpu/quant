"""Which registry symbols have FROZEN bars: the file is fresh, the prices are not (2026-11-04).

THE DEFECT. Fusion stopped quoting UST10Y and UST05Y around 2025-12-31, yet their parquet files
keep a fresh mtime because the refresher rewrites them every pass. Every freshness check the desk
had read the mtime, so five generators (cell_emitter_sources, culture_gap_recipes,
converter_vocabulary, free_stack_sources and the cross_asset_residual factor lists) kept minting
cells on them. A cell on a frozen series spends a trial from the shared family-wise budget, raises
the deflated-Sharpe bar for every live FX and metals cell, and can never trade or clock forward.

THE MEASUREMENT. The last bar's timestamp, read from the parquet footer's column statistics (about
2 ms a file, no data pages decoded), compared with the MEDIAN last bar of the same universe.
Relative, never against the wall clock, and against the median, never the freshest: the box
refreshes FX majors hourly and the equity/exotic leg days behind (measured 2026-08-28: 24 symbols
within 2 days, 166 three days back), and a stalled refresh leg that holds most of the universe
moves the median with it. So neither an upstream outage nor one slow leg can empty the compiler's
universe; only a MINORITY of series that stopped while the rest moved is called frozen. A
symbol is frozen only on POSITIVE evidence (a readable last bar more than STALE_BAR_DAYS behind
the median); an unreadable or unstamped file is UNMEASURED and stays in.

Revert without a push: create desks/mt5/data/STALE_BAR_GUARD_OFF.

A LIBRARY, NOT AN ORGAN: it runs on the clock of the compiler leg that imports it
(`miner_candidate_compiler.live_known_symbols`) and of the deepening worker.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
UNIVERSE = DESK / "data" / "universe"
REPORT = DESK / "reports" / "STALE_BARS.json"
SWITCH_OFF = DESK / "data" / "STALE_BAR_GUARD_OFF"

#: Two weeks covers every venue holiday run with room to spare; a live symbol never lags the
#: median one by that much.
STALE_BAR_DAYS = 14.0


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):  # epoch nanoseconds, the pandas encoding
        try:
            return datetime.fromtimestamp(float(value) / 1e9, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def last_bar(path: Path) -> datetime | None:
    """The newest bar time in one bars parquet, or None when it cannot be read."""
    try:
        import pyarrow.parquet as pq

        f = pq.ParquetFile(path)
        schema = f.schema_arrow
        meta = schema.pandas_metadata or {}
        idx = [c for c in meta.get("index_columns") or [] if isinstance(c, str)]
        col = idx[0] if idx else "time"
        i = schema.get_field_index(col)
        if i < 0:
            return None
        best: datetime | None = None
        for g in range(f.metadata.num_row_groups):
            stats = f.metadata.row_group(g).column(i).statistics
            if stats is None or not stats.has_min_max:
                return None  # unstamped: UNMEASURED, never frozen
            t = _as_utc(stats.max)
            if t is None:
                return None
            best = t if best is None or t > best else best
        return best
    except Exception:
        return None


def measure(
    universe: Path | None = None, chart: str = "H1", max_lag_days: float = STALE_BAR_DAYS
) -> dict[str, Any]:
    """Every symbol's last bar and lag behind the median; the frozen ones named."""
    root = universe or UNIVERSE
    last: dict[str, datetime | None] = {}
    for p in sorted(root.glob(f"*_{chart}.parquet")):
        last[p.stem.removesuffix(f"_{chart}")] = last_bar(p)
    read = [t for t in last.values() if t is not None]
    if not read:
        return {
            "verdict": "UNMEASURED",
            "reason": "no readable last bar",
            "chart": chart,
            "symbols": len(last),
            "frozen": {},
            "unmeasured": sorted(last),
        }
    ordered = sorted(read)
    reference = ordered[(len(ordered) - 1) // 2]  # lower median: never a single fresh outlier
    frozen = {
        s: round((reference - t).total_seconds() / 86400, 1)
        for s, t in last.items()
        if t is not None and (reference - t).total_seconds() / 86400 > max_lag_days
    }
    return {
        "verdict": "FROZEN_FOUND" if frozen else "ALL_FRESH",
        "chart": chart,
        "max_lag_days": max_lag_days,
        "reference": "median_last_bar",
        "median_last_bar": reference.isoformat(),
        "freshest_bar": ordered[-1].isoformat(),
        "symbols": len(last),
        "frozen": dict(sorted(frozen.items(), key=lambda kv: -kv[1])),
        "frozen_last_bar": {s: t.isoformat() for s in frozen if (t := last[s]) is not None},
        "unmeasured": sorted(s for s, t in last.items() if t is None),
    }


def live_symbols(
    symbols: set[str], universe: Path | None = None, publish: bool = True
) -> tuple[set[str], dict[str, Any]]:
    """`symbols` minus the frozen ones, and the measurement that decided it.

    Never raises: a failure of the measurement keeps every symbol (UNMEASURED is not FROZEN).
    """
    if SWITCH_OFF.exists():
        return set(symbols), {"verdict": "SWITCHED_OFF", "switch": str(SWITCH_OFF)}
    try:
        doc = measure(universe)
    except Exception as exc:  # pragma: no cover - host-dependent
        return set(symbols), {"verdict": "UNMEASURED", "reason": type(exc).__name__}
    frozen = set(doc.get("frozen") or {})
    kept = {s for s in symbols if s not in frozen}
    doc["withheld_from_minting"] = sorted(set(symbols) & frozen)
    # MISSED GROWTH (GROWTH_GOVERNANCE Rule 1). A cell on a frozen series has no forward bar to
    # clock and no live quote to trade, so its expected contribution to forward E[log W] is zero
    # while its trial is still charged against every cell that can trade. Withholding it is
    # therefore growth-neutral at worst and lowers the multiple-testing bar for the rest.
    doc["missed_growth"] = {
        "mechanism": "stale_bar_guard",
        "withheld_symbols": len(doc["withheld_from_minting"]),
        "expected_delta_elog": 0.0,
        "basis": "no forward bars and no venue quote on a frozen series; trials saved instead",
    }
    if publish:
        try:
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            tmp = REPORT.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {"measured_at": datetime.now(UTC).isoformat(timespec="seconds"), **doc},
                    indent=1,
                ),
                "utf-8",
            )
            tmp.replace(REPORT)
        except OSError:  # pragma: no cover - read-only host
            pass
    return kept, doc
