"""TDA STATE -- persistence-landscape fragility of the multi-symbol return cloud, as a conditioner.

WHAT IT MEASURES (Gidea & Katz 2018, "Topological data analysis of financial time series").
Take the last `WINDOW` hourly returns of a cross-asset basket (FX majors, gold, silver, equity
indices, crude: whichever of `BASKET` are hypothesis-lane and have bars) as a cloud of `WINDOW`
points in R^k. Build its Vietoris-Rips filtration, read the persistence diagrams, turn each into
a persistence LANDSCAPE (the first `LAYERS` tent-function envelopes) and take its L1 and L2 norms.
Calm, diffuse markets give a tight, structureless cloud and small norms; before and during
stress the cloud stretches and loops, and the norms rise. The norm's z against the previous
`Z_WINDOW` hours is the fragility state.

THE ENGINE. Diagrams come from `libs.research.adapters.ripser.diagrams` -- the existing adapter.
With `ripser` importable it gives H0 and H1; without it H0 is still exact (the Rips H0 deaths are
the minimum spanning tree's edge lengths) and H1 is NULL, never approximated. So the series has
two families of columns: `h0_*` / `fragility_z` (always measured, the conditioner) and `h1_*` /
`h1_z` (measured only where ripser is installed; each row names its `engine`).

EACH COLUMN IS SCALED BY ITS OWN TRAILING VOLATILITY (`VOL_WINDOW` bars ending at the row), so
crude's moves do not drown EURUSD's and the topology describes co-movement, not one asset's size.

NO LOOKAHEAD, BY CONSTRUCTION AND BY TEST. Bar t's row uses returns up to and including bar t's
close and nothing after; it is stamped `available_time` = the true UTC of bar t's close (bars are
labelled by their broker-clock open; see `state_conditioner`). `tests/research/test_tda_state.py`
appends a violent bar after t and asserts every row up to t is unchanged.

WHAT IT PUBLISHES (data department, hourly leg `tda_state`):

    reports/TDA_STATE.json                 the latest fragility, the basket, the engine, minting
    data/lake/series/tda_fragility.csv     the PIT series (exogenous_conditioner / alt:)
    data/lake/state/tda_state.json         the minted cell ids

BOUNDED: at most `MAX_ROWS_PER_PASS` new windows a pass (oldest first, resumed next pass) and a
wall-clock `--budget-s`. NOT MONEY PATH: it reads bars and writes a report, a series, a donation.

    python desks/mt5/research/tda_state.py --once
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import state_conditioner as sc  # noqa: E402

SEAT = "tda_state"
SID = "tda_fragility"
REPORT = sc.REPORTS / "TDA_STATE.json"
STATE = sc.STATE_DIR / "tda_state.json"
BARS = DESK / "data" / "universe"

BASKET: tuple[str, ...] = ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "XAUUSD",
                           "XAGUSD", "US500", "NAS100", "US30", "GER40", "UK100", "JPN225",
                           "XTIUSD", "XBRUSD")
MIN_SYMBOLS = 4
#: Hours in one point cloud, hours of trailing volatility each column is scaled by (and the
#: minimum before a scale exists), landscape layers and grid resolution.
WINDOW = 48
VOL_WINDOW = 500
VOL_MIN = 100
LAYERS = 5
GRID = 128
Z_WINDOW = 500
Z_MIN = 48
#: First pass reaches this many hours back; each pass computes at most MAX_ROWS_PER_PASS rows.
BACKFILL_ROWS = 24 * 260
MAX_ROWS_PER_PASS = 2_500
MAX_ROWS = 24 * 400
MIN_ROWS_TO_MINT = 500
COLUMNS = ("n_symbols", "engine", "h0_l1", "h0_l2", "h1_l1", "h1_l2", "fragility_z", "h1_z")


# ------------------------------------------------------------------------- landscapes and norms
_trapz = getattr(np, "trapezoid", None) or np.trapz  # numpy 2 renamed it; the box may lag


def landscape_norms(dgm: np.ndarray, layers: int = LAYERS, grid: int = GRID
                    ) -> tuple[float, float]:
    """(L1, L2) norms of the persistence landscape of one diagram; infinite bars dropped."""
    d = np.asarray(dgm, dtype=float).reshape(-1, 2)
    d = d[np.isfinite(d).all(axis=1) & (d[:, 1] > d[:, 0])]
    if d.size == 0:
        return 0.0, 0.0
    lo, hi = float(d[:, 0].min()), float(d[:, 1].max())
    xs = np.linspace(lo, hi, grid)
    tents = np.maximum(0.0, np.minimum(xs[None, :] - d[:, :1], d[:, 1:] - xs[None, :]))
    k = min(layers, tents.shape[0])
    lam = -np.sort(-tents, axis=0)[:k]                # lambda_1 >= lambda_2 >= ... per x
    dx = (hi - lo) / (grid - 1) if grid > 1 else 0.0
    l1 = float(_trapz(lam, dx=dx, axis=1).sum()) if dx > 0 else 0.0
    l2 = float(math.sqrt(_trapz(lam ** 2, dx=dx, axis=1).sum())) if dx > 0 else 0.0
    return l1, l2


def _diagrams(cloud: np.ndarray) -> tuple[list[np.ndarray], str]:
    from libs.research.adapters import ripser as adapter
    return adapter.diagrams(cloud, maxdim=1)


def window_row(scaled: np.ndarray) -> dict[str, Any]:
    dg, engine = _diagrams(scaled)
    # H0 bars all start at 0, so its top few layers are just the few longest MST edges and sit
    # still for hours; every layer is kept so each edge of the cloud moves the norm.
    h0 = landscape_norms(dg[0], layers=scaled.shape[0])
    out: dict[str, Any] = {"n_symbols": int(scaled.shape[1]), "engine": engine,
                           "h0_l1": h0[0], "h0_l2": h0[1], "h1_l1": None, "h1_l2": None}
    if engine == "ripser" and len(dg) > 1:
        h1 = landscape_norms(dg[1])
        out["h1_l1"], out["h1_l2"] = h1
    return out


# ------------------------------------------------------------------------------------- the data
def load_returns(symbols: Sequence[str], bars: Path) -> pd.DataFrame:
    """Hourly log returns, inner-joined on the broker-labelled bar index."""
    cols: dict[str, pd.Series] = {}
    for s in symbols:
        p = bars / f"{s}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p, columns=["close"])
        except Exception:
            continue
        idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
        c = pd.Series(pd.to_numeric(df["close"], errors="coerce").to_numpy(), index=idx)
        c = c[c.index.notna() & (c > 0)]
        c = c[~c.index.duplicated(keep="last")].sort_index()
        if len(c) > VOL_MIN + WINDOW:
            cols[s] = np.log(c).diff()
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).dropna(how="any")


def scaled_returns(r: pd.DataFrame) -> pd.DataFrame:
    """Each column over its trailing std (window ENDS at the row: nothing later is used)."""
    sd = r.rolling(VOL_WINDOW, min_periods=VOL_MIN).std(ddof=0)
    return (r / sd.replace(0.0, np.nan)).dropna(how="any")


def rows_for(scaled: pd.DataFrame, positions: Sequence[int]) -> list[dict[str, Any]]:
    """One row per position p >= WINDOW-1, from scaled rows [p-WINDOW+1, p] only."""
    a = scaled.to_numpy(dtype=float)
    out: list[dict[str, Any]] = []
    for p in positions:
        if p < WINDOW - 1 or p >= a.shape[0]:
            continue
        row = window_row(a[p - WINDOW + 1:p + 1])
        bar = scaled.index[p]
        wall = bar.tz_convert(UTC).tz_localize(None).to_pydatetime() + timedelta(hours=1)
        close_utc = sc.broker_to_utc(wall)
        out.append({"event_time": sc.iso(close_utc), "available_time": sc.iso(close_utc),
                    "broker_bar": bar.tz_convert(UTC).tz_localize(None).isoformat(), **row})
    return out


def basket(bars: Path) -> tuple[list[str], dict[str, str]]:
    try:
        from research.universe_policy import HYPOTHESIS, lane
    except Exception:
        lane, HYPOTHESIS = None, None
    keep: list[str] = []
    aside: dict[str, str] = {}
    for s in BASKET:
        if lane is not None and lane(s) != HYPOTHESIS:
            aside[s] = f"lane {lane(s)}"
        elif not (bars / f"{s}_H1.parquet").exists():
            aside[s] = "no H1 bars on this host"
        else:
            keep.append(s)
    return keep, aside


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ------------------------------------------------------------------------------------- one pass
def run(*, budget_s: float = 180.0, bars: Path = BARS, series_root: Path | None = None,
        state_path: Path = STATE, report: Path | None = REPORT, dry_run: bool = False,
        now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now_utc = now or datetime.now(UTC)
    syms, aside = basket(bars)
    doc: dict[str, Any] = {"generated_utc": sc.iso(now_utc), "organ": SEAT, "basket": syms,
                           "set_aside": aside, "window_h": WINDOW, "vol_window_h": VOL_WINDOW,
                           "landscape_layers": LAYERS, "budget_s": budget_s}
    old = sc.read_series(SID, series_root)
    scaled = scaled_returns(load_returns(syms, bars)) if len(syms) >= MIN_SYMBOLS \
        else pd.DataFrame()
    if scaled.empty or scaled.shape[1] < MIN_SYMBOLS:
        doc.update(verdict="UNMEASURED",
                   why=f"{scaled.shape[1] if not scaled.empty else 0} basket symbols with "
                       f"aligned scaled returns; need {MIN_SYMBOLS}", rows=len(old))
        if report is not None and not dry_run:
            sc.write_json(report, doc)
        return doc
    # A changed basket is a different cloud: the series restarts rather than splicing two.
    if old and str(old[-1].get("basket") or "") != ",".join(scaled.columns):
        old = []
    labels = [b.tz_convert(UTC).tz_localize(None).isoformat() for b in scaled.index]
    last = str(old[-1].get("broker_bar")) if old else ""
    start = max(WINDOW - 1, len(labels) - BACKFILL_ROWS)
    if last:
        start = max(start, next((i for i, lb in enumerate(labels) if lb > last), len(labels)))
    # The newest bar is labelled by its open; it is complete only once its hour has passed.
    newest_ok = len(labels)
    while newest_ok > 0:
        wall = datetime.fromisoformat(labels[newest_ok - 1]) + timedelta(hours=1)
        if sc.broker_to_utc(wall) <= now_utc:
            break
        newest_ok -= 1
    positions = list(range(start, newest_ok))
    todo = positions[:MAX_ROWS_PER_PASS]
    new: list[dict[str, Any]] = []
    for i in range(0, len(todo), 100):
        if time.monotonic() - t0 > budget_s:
            break
        new += rows_for(scaled, todo[i:i + 100])
    hist0 = [_f(r.get("h0_l1")) for r in old]
    hist1 = [_f(r.get("h1_l1")) for r in old]
    z0 = sc.trailing_z([*hist0, *[r["h0_l1"] for r in new]], Z_WINDOW, Z_MIN)[len(hist0):]
    z1 = sc.trailing_z([*hist1, *[r["h1_l1"] for r in new]], Z_WINDOW, Z_MIN)[len(hist1):]
    stamp = sc.iso(now_utc)
    for r, a, b in zip(new, z0, z1, strict=True):
        r.update(fragility_z=a, h1_z=b, retrieval_time=stamp, source_id=SEAT,
                 basket=",".join(scaled.columns))
    rows = [*old, *new][-MAX_ROWS:]
    if new and not dry_run:
        sc.write_series(SID, rows, ("broker_bar", "retrieval_time", "basket", *COLUMNS),
                        series_root)
    grid: list[dict[str, Any]] = []
    if len(rows) >= MIN_ROWS_TO_MINT:
        sigs = ["fragility_z"]
        if sum(1 for r in rows if _f(r.get("h1_z")) is not None) >= MIN_ROWS_TO_MINT:
            sigs.append("h1_z")
        for s in scaled.columns:
            grid += sc.cell_rows(SEAT, SID, s, sigs,
                                 "persistence-landscape fragility of the cross-asset hourly "
                                 f"return cloud as a regime state conditioning {s}")
    minted = sc.mint_once(SEAT, grid, state_path, dry_run=dry_run)
    lt = rows[-1] if rows else {}
    doc.update(verdict="MEASURED" if rows else "UNMEASURED", rows=len(rows), new_rows=len(new),
               behind_rows=max(0, newest_ok - start - len(new)),
               engine=lt.get("engine"), latest={
                   "broker_bar": lt.get("broker_bar"), "available_time": lt.get("available_time"),
                   **{k: (lt.get(k) if k == "engine" else _f(lt.get(k))) for k in COLUMNS}},
               conditioner=sc.conditioner_specs(SID, "fragility_z"), minting=minted,
               registered_as={"lake_series": f"data/lake/series/{SID}.csv",
                              "family": "exogenous_conditioner (signal fragility_z | h1_z)",
                              "second_axis": f"params.conditioner = alt:{SID}:fragility_z:gt:2"},
               elapsed_s=round(time.monotonic() - t0, 2))
    if report is not None and not dry_run:
        sc.write_json(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=180.0)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run)
    print(f"tda_state: {doc['verdict']} rows={doc.get('rows')} new={doc.get('new_rows')} "
          f"engine={doc.get('engine')} elapsed={doc.get('elapsed_s')}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
