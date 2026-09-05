"""Drift AHEAD: forecast the next window's distribution per instrument, and ask whether the
book's correlation topology has moved -- before the drawdown teaches it.

TWO DRIFTS, ONE VERDICT. Per instrument, `libs.regime.drift` summarises each broker day of H1
bars by declared statistics (vol, range, breakout hit-rate, spread rank, |ret|), fits a learned
lag weighting on how past windows predicted their successors, and reports the NEXT window's
forecast as a z against the long-run baseline. `hazard_max` is the largest |z| across the
statistics; measured 2026-09-04 on the desk's own bars it sits at 0.81 (EURUSD), 0.81 (XAUUSD)
and 0.91 (USDJPY) -- STABLE, and below the WATCH line at 1.0 by a margin that says the line is
not decorative. Per book, `libs.portfolio.latent_factors.drift` asks whether the recent 30 days'
sleeve correlation matrix sits farther from the EW long-run matrix than past 30-day blocks did,
in units of those blocks' own dispersion; `tail_dependence` and the k-factor model are reported
recent-vs-prior beside it, because the bad-state picture is the one capital is sized on.

    verdict = STRUCTURE_SHIFTED   the book's correlation topology moved (structure z > 2)
            | DRIFT_AHEAD         some instrument's forecast hazard_max > 2
            | WATCH               some instrument's hazard_max > 1
            | STABLE              nothing above the lines

THE REPORT IS THE PRODUCT. No tasks leave here. `revival_engine` reads `verdict` from
reports/DRIFT.json to decide whether STATE_FRAGILE burials deserve a second look, and the
allocator's crisis overlay is the other intended listener. `what_changed` is the compact list of
(symbol, statistic, z) that moved, so a reader does not have to walk per_symbol to learn why.

DEGRADES WITH A REASON, NEVER SILENTLY. Off-box (measured 2026-09-04) the canon still names 14
book instruments but the shadow ledgers hold 14 days of 50 sleeves against the 90 rows structure
drift needs, so the verdict was WATCH on EURGBP's range forecast (z = -1.06) with structure
UNMEASURED and the reason written beside it. A tree with no canon falls back to the instruments
that have bars; every such substitution is a `why` string on the report and a line in
`degraded`, and the verdict is computed from whatever WAS measurable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio import latent_factors as lf  # noqa: E402
from libs.regime.drift import forecast_next, window_stats  # noqa: E402
from research import proposer_common as pc  # noqa: E402

REPORT = _DESK / "reports" / "DRIFT.json"
#: One window is one broker day of H1 bars: the clock the allocator re-sizes on.
WINDOW = 24
#: Windows the forecast is fitted on. 750 days is the long-run baseline the hazard is measured
#: against -- long enough that one quarter's vol regime does not become "normal", short enough
#: to stay bounded on a 53,899-bar frame (the fit itself is a least-squares on 750 rows).
LOOKBACK_BARS = WINDOW * 750
MIN_BARS = 3000
#: Fallback breadth when the certified book is empty (off-box): enough instruments to see a
#: market-wide move, few enough that the report stays readable.
FALLBACK_CAP = 12
#: Structure drift compares the last RECENT_DAYS of daily sleeve P&L with the long run. 30 is the
#: shortest window on which a 50-sleeve correlation matrix is a matrix rather than noise, and
#: `latent_factors.drift` needs three such blocks of history before it will say anything.
RECENT_DAYS = 30
MIN_SLEEVES = 2
WATCH_Z, DRIFT_Z = 1.0, 2.0
STABLE, WATCH, DRIFT_AHEAD, STRUCTURE_SHIFTED, UNMEASURED = (
    "STABLE", "WATCH", "DRIFT_AHEAD", "STRUCTURE_SHIFTED", "UNMEASURED")


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:
        return []


def _n_bars(path: Path) -> int:
    """Row count from the parquet footer, so choosing a fallback set does not load 24 frames."""
    try:
        import pyarrow.parquet as pq
        return int(pq.read_metadata(path).num_rows)
    except Exception:
        d = pc.bars(path.stem.removesuffix("_H1"))
        return 0 if d is None else len(d)


def _symbols(symbols: list[str] | None) -> tuple[list[str], dict[str, str]]:
    """Which instruments to watch, and why those. Explicit > certified book > fallback."""
    have = {p.stem.removesuffix("_H1"): p for p in pc.UNI.glob("*_H1.parquet")}
    if symbols:
        return sorted({s for s in symbols if s in have}), {"source": "explicit", "why": ""}
    book = [s for s in _book_symbols() if s in have]
    if book:
        return sorted(set(book)), {"source": "book", "why": ""}
    fallback = sorted(s for s, p in have.items() if _n_bars(p) >= MIN_BARS)[:FALLBACK_CAP]
    return fallback, {"source": "fallback",
                      "why": (f"certified book empty on this tree; watching up to {FALLBACK_CAP} "
                              f"instruments with >= {MIN_BARS} H1 bars instead")}


def symbol_drift(d: pd.DataFrame) -> dict[str, Any]:
    """Next-window forecast hazard for one instrument, from its own declared statistics."""
    stats = window_stats(d.tail(LOOKBACK_BARS), window=WINDOW)
    fc = forecast_next(stats)
    per_stat = {col: {k: v for k, v in row.items() if k in ("forecast", "baseline", "z")}
                for col, row in (fc.get("per_stat") or {}).items()}
    return {"hazard_max": fc.get("hazard_max"), "verdict": fc.get("verdict") or UNMEASURED,
            "hazard": fc.get("hazard") or {}, "per_stat": per_stat, "n_windows": len(stats),
            "why": fc.get("why", "")}


def _load_trades() -> list[Any]:
    try:
        from research.state_admission_run import load_trades
        return list(load_trades("shadow"))
    except Exception:
        return []


def daily_pnl_matrix(trades: list[Any]) -> tuple[np.ndarray | None, list[str], str]:
    """Days x sleeves of realised shadow R, zero where a sleeve did not trade that day.

    Zero-filling is the honest choice for a correlation of OUTCOMES: a sleeve that sat out a day
    earned nothing on it, and leaving NaN would let pandas compute each pair on a different set
    of days and call the result one matrix.
    """
    rows = []
    for t in trades:
        try:
            when = pd.Timestamp(t.when)
            when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
            rows.append((str(t.sleeve), when.normalize(), float(t.r)))
        except (TypeError, ValueError, AttributeError):
            continue
    if not rows:
        return None, [], "no shadow trades: no ledger_*.json under reports/shadow or backups"
    frame = pd.DataFrame(rows, columns=["sleeve", "day", "r"])
    piv = frame.pivot_table(index="day", columns="sleeve", values="r", aggfunc="sum",
                            fill_value=0.0).sort_index()
    sleeves = [str(c) for c in piv.columns]
    if len(sleeves) < MIN_SLEEVES:
        return None, sleeves, f"need {MIN_SLEEVES} sleeves for a correlation, have {len(sleeves)}"
    return piv.to_numpy(dtype=float), sleeves, ""


def structure_drift(m: np.ndarray | None, sleeves: list[str], why: str = "") -> dict[str, Any]:
    """Has the book's latent-factor structure moved? recent RECENT_DAYS vs the long run."""
    if m is None:
        return {"verdict": UNMEASURED, "z": None, "why": why or "no P&L matrix"}
    dr = lf.drift(m, recent=RECENT_DAYS)
    out: dict[str, Any] = {"verdict": dr.get("verdict") or UNMEASURED, "z": dr.get("z"),
                           "distance": dr.get("distance"), "baseline_mean": dr.get("baseline_mean"),
                           "windows": dr.get("windows"), "why": dr.get("why", ""),
                           "n_days": int(m.shape[0]), "n_sleeves": int(m.shape[1]),
                           "recent_days": RECENT_DAYS}
    if m.shape[0] < 2 * RECENT_DAYS:
        out["tail_dependence"] = {"why": f"need {2 * RECENT_DAYS} days for recent-vs-prior"}
        return out
    now, prior = m[-RECENT_DAYS:], m[:-RECENT_DAYS]
    off = ~np.eye(m.shape[1], dtype=bool)
    try:
        td_now, td_prior = lf.tail_dependence(now), lf.tail_dependence(prior)
        out["tail_dependence"] = {
            "recent_mean": round(float(td_now[off].mean()), 4),
            "prior_mean": round(float(td_prior[off].mean()), 4),
            "recent_max": round(float(td_now[off].max()), 4),
            "prior_max": round(float(td_prior[off].max()), 4)}
        k = int(min(3, m.shape[1]))
        out["factor_explained"] = {
            "recent": round(float(lf.factor_model(now, k=k)["explained"]), 4),
            "prior": round(float(lf.factor_model(prior, k=k)["explained"]), 4)}
        # THE FOUR HEATS ON AN EQUAL-WEIGHT BOOK: what 1/N nominal is really made of today. The
        # allocator sizes its own book; this is the structure's own statement, weight-free.
        ev = [SimpleNamespace(name=s, daily_r=m[:, i]) for i, s in enumerate(sleeves)]
        heats = lf.effective(ev, {s: 1.0 / len(sleeves) for s in sleeves})
        out["heats_equal_weight"] = {k: heats.get(k) for k in (
            "nominal", "covariance", "factor", "tail", "effective", "n_eff",
            "factor_explained", "max_tail_dependence", "stress_days")}
    except Exception as exc:
        out["tail_dependence"] = {"why": f"{type(exc).__name__}: {exc}"}
    return out


def what_changed(per_symbol: dict[str, dict[str, Any]], structure: dict[str, Any],
                 limit: int = 40) -> list[dict[str, Any]]:
    """The compact answer to 'why this verdict': every (symbol, statistic) past the WATCH line."""
    out: list[dict[str, Any]] = []
    for sym, row in per_symbol.items():
        for stat, s in (row.get("per_stat") or {}).items():
            z = s.get("z")
            if z is not None and abs(float(z)) >= WATCH_Z:
                out.append({"symbol": sym, "stat": stat, "z": float(z),
                            "forecast": s.get("forecast"), "baseline": s.get("baseline")})
    z = structure.get("z")
    if z is not None and float(z) >= WATCH_Z:
        out.append({"symbol": "BOOK", "stat": "correlation_structure", "z": float(z),
                    "forecast": structure.get("distance"),
                    "baseline": structure.get("baseline_mean")})
    out.sort(key=lambda r: -abs(r["z"]))
    return out[:limit]


def verdict(per_symbol: dict[str, dict[str, Any]], structure: dict[str, Any]) -> str:
    """STRUCTURE_SHIFTED outranks the per-instrument lines: a book whose sleeves have collapsed
    onto one factor is the larger fact whatever any single instrument's vol is doing next."""
    if structure.get("verdict") == STRUCTURE_SHIFTED:
        return STRUCTURE_SHIFTED
    hz = [float(r["hazard_max"]) for r in per_symbol.values() if r.get("hazard_max") is not None]
    if hz and max(hz) > DRIFT_Z:
        return DRIFT_AHEAD
    if hz and max(hz) > WATCH_Z:
        return WATCH
    return STABLE


def run(symbols: list[str] | None = None, budget_s: float = 300.0, write: bool = True) -> dict:
    todo, chosen = _symbols(symbols)
    per_symbol: dict[str, dict[str, Any]] = {}
    skipped: dict[str, str] = {}
    degraded: list[str] = []
    if chosen["why"]:
        degraded.append(chosen["why"])
    started = time.monotonic()
    for sym in todo:
        if time.monotonic() - started > budget_s:
            skipped[sym] = "budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            skipped[sym] = f"under {MIN_BARS} H1 bars"
            continue
        try:
            per_symbol[sym] = symbol_drift(d)
        except Exception as exc:
            skipped[sym] = f"{type(exc).__name__}: {exc}"
    if not per_symbol:
        degraded.append("no instrument measured: per-symbol hazard absent from the verdict")
    m, sleeves, why = daily_pnl_matrix(_load_trades())
    structure = structure_drift(m, sleeves, why)
    if structure.get("verdict") == UNMEASURED or structure.get("z") is None:
        degraded.append(f"structure drift unmeasured: {structure.get('why') or 'no z'}")
    sym_hz = [float(r["hazard_max"]) for r in per_symbol.values()
              if r.get("hazard_max") is not None]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "verdict": verdict(per_symbol, structure),
           "symbol_verdict": (DRIFT_AHEAD if sym_hz and max(sym_hz) > DRIFT_Z else
                              WATCH if sym_hz and max(sym_hz) > WATCH_Z else
                              STABLE if sym_hz else UNMEASURED),
           "structure_verdict": structure.get("verdict") or UNMEASURED,
           "hazard_max": (round(max(sym_hz), 3) if sym_hz else None),
           "per_symbol": per_symbol, "structure": structure,
           "what_changed": what_changed(per_symbol, structure),
           "symbols": {**chosen, "n": len(todo)}, "skipped": skipped, "degraded": degraded,
           "lines": {"watch_z": WATCH_Z, "drift_z": DRIFT_Z, "window_bars": WINDOW,
                     "lookback_bars": LOOKBACK_BARS, "recent_days": RECENT_DAYS},
           "rule": ("STRUCTURE_SHIFTED if the book's correlation topology moved (structure z > "
                    f"{DRIFT_Z}); else DRIFT_AHEAD if any instrument's next-window hazard_max > "
                    f"{DRIFT_Z}; else WATCH if > {WATCH_Z}; else STABLE. Consumers: "
                    "revival_engine (STATE_FRAGILE burials), the allocator's crisis overlay.")}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    doc = run(symbols=a.symbol, budget_s=a.budget_s, write=not a.no_write)
    print(f"DRIFT  verdict={doc['verdict']}  symbols={doc['symbol_verdict']} "
          f"(hazard_max={doc['hazard_max']})  structure={doc['structure_verdict']} "
          f"(z={doc['structure'].get('z')})  watched={doc['symbols']['n']} "
          f"[{doc['symbols']['source']}]")
    for r in doc["what_changed"][:12]:
        print(f"  {r['symbol']:10s} {r['stat']:22s} z={r['z']:+.2f}  forecast={r['forecast']} "
              f"baseline={r['baseline']}")
    for w in doc["degraded"]:
        print(f"  DEGRADED: {w}")
    if not a.no_write:
        print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
