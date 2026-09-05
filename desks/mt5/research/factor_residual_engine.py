"""Strip every MT5 instrument down to its economic drivers and hunt what is left.

    r_XAU,t = a + b1*r_USDX,t + b2*r_UST10Y,t + b3*r_XAG,t + b4*r_US500,t + eps_t

and eps is the object of interest. `economic_drivers` states 543 such claims across 247
instruments -- one per (instrument, named driver set) -- and this module measures each one and
proposes the survivors to the gauntlet as ordinary candidates.

WHAT THIS IS AND IS NOT. It is a PROPOSER. It computes the residual exactly as
`family_cross_asset_residual` computes it -- same causal-beta primitive, same window arithmetic
-- screens it against the desk's own round-trip cost, deflates what it finds by the number of
things it looked at, and writes the survivors into the miner-discovery contract. From there the
ordinary hourly path takes over: `miner_candidate_compiler` admits them as EXACT_RECIPE,
`external_gauntlet` runs the ten gates, `shadow_forward` clocks forward evidence and
`pf_allocator` prices the survivor against every other sleeve. It admits nothing itself and it
cannot: there is no second door into the candidate store, and this one only knocks.

WHY THE SCREEN MUST DEFLATE ITSELF. `gate_policy` charges the deflated Sharpe a FIXED campaign
size (597 trials) rather than the size of whatever batch a cell was scheduled into -- deliberately,
so a candidate's bar does not move with the hour it arrived in. That is right for the gate and it
means a proposer emitting hundreds of cells would be handing the gauntlet a multiplicity problem
the gauntlet has been told not to price. So this pays for its own search: every (target, driver
set, horizon, threshold, side) tested this run is counted, and a cell is proposed only when its
non-overlapping t survives `multiplicity.deflate_t` against that count AND its expectancy clears
the round trip. The census is written into the report so the deflation can be checked rather than
believed.

FOUR WAYS THIS COULD BE A LIE, AND WHAT STOPS EACH

1. BETAS THAT HAVE SEEN THE BAR. `mt5desk.causal_residual` fits beta[t] on [t-win, t-1] only.
   This is the error that made the executable family fail 348 times and certify nothing.

2. OVERLAPPING SAMPLES. An h-bar forward return sampled every bar shares h-1 bars with its
   neighbour, so the naive t is inflated by roughly sqrt(h). Only hits separated by at least h
   bars are kept, and both t values are reported so the gap is visible.

3. AN EDGE MEASURED IN SIGMA AND SPENT IN DOLLARS. Every horizon is scored against the round trip
   computed from `Costs.from_symbol` on the desk's own contract terms -- the corrected one, with
   the commission converted through `quote_per_account`.

4. A DIRECTION CHOSEN AFTER THE FACT. Reversion and continuation are BOTH tested and both are
   charged to the trial count. Picking the sign that happened to pay and then reporting one test
   is the oldest way to manufacture a residual edge.

Usage:
    python research/factor_residual_engine.py                  # sweep, screen, propose
    python research/factor_residual_engine.py --shuffle        # the null: expect ~nothing
    python research/factor_residual_engine.py --target XAUUSD  # one instrument, verbose
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.causal_residual import causal_residual                      # noqa: E402
from mt5desk.economic_drivers import DriverSet, universe_driver_sets     # noqa: E402
from mt5desk.engine import Costs                                         # noqa: E402
from research.multiplicity import deflate_t, expected_max_z              # noqa: E402

UNI = _DESK / "data" / "universe"
INTEL = _DESK / "data" / "intelligence" / "factor_residual"
REPORT = _DESK / "reports" / "factor_residual.json"

#: Bars the causal betas are fitted on, and bars the residual's own level is z-scored over.
#: Both are passed through onto the candidate so the gauntlet rebuilds the same object.
BETA_WIN = 240
Z_WIN = 240
#: Forward horizons in H1 bars: a session, a day, three days, a week.
HORIZONS = (8, 24, 72, 120)
ENTRY_Z = (2.0, 2.5, 3.0)
SIDE_MODES = ("revert", "continue")

#: A cell needs this many independent hits before its mean says anything. Below it the standard
#: error is wider than any expectancy the screen could measure, so the cell is counted as a trial
#: and dropped rather than proposed on a handful of observations.
MIN_INDEPENDENT = 30
#: Deflated-t bar for PROPOSING. This is a proposer's threshold, not a gate: the ten gates are
#: unchanged and remain the only thing that can certify. It exists so the gauntlet is handed
#: hypotheses that already paid for the search that found them.
PROPOSE_T = 2.0
#: The panel is an inner join, so a short driver truncates the target too. Below this there is
#: not room for beta_win + 2*z_win plus a forward horizon and an honest sample after it.
MIN_PANEL_BARS = BETA_WIN + Z_WIN * 2 + max(HORIZONS) + 500


def _bars(sym: str) -> pd.DataFrame | None:
    path = UNI / f"{sym}_H1.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, ImportError, KeyError):
        return None
    if df.empty:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index))
    return df


def _cost_frac(sym: str, meta: dict, close: pd.Series) -> float | None:
    """Round trip as a fraction of price -- the unit every expectancy below is measured in."""
    row = meta.get(sym)
    if not isinstance(row, dict):
        return None
    try:
        costs = Costs.from_symbol(row, mult=2.0)
        px = float(close.iloc[-1])
        if not math.isfinite(px) or px <= 0:
            return None
        return float((costs.per_oz_roundtrip() / costs.contract_oz) / px)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def panel(ds: DriverSet, cache: dict[str, pd.DataFrame | None]) -> pd.DataFrame | None:
    """Log returns of the target and its drivers on one shared index, inner-joined."""
    frames = {}
    for sym in (ds.target, *ds.drivers):
        if sym not in cache:
            cache[sym] = _bars(sym)
        df = cache[sym]
        if df is None:
            return None
        frames[sym] = df["close"].astype(float)
    joined = pd.DataFrame(frames).dropna()
    if len(joined) < MIN_PANEL_BARS:
        return None
    return np.log(joined).diff().dropna()


def residual_z(ret: pd.DataFrame, ds: DriverSet) -> pd.Series:
    """The z-score of the cumulative causal residual -- the exact quantity the family trades."""
    y = ret[ds.target].to_numpy()
    X = ret[list(ds.drivers)].to_numpy()
    eps = pd.Series(causal_residual(y, X, BETA_WIN), index=ret.index)
    cum = eps.fillna(0.0).cumsum().where(eps.notna())
    mu = cum.rolling(Z_WIN).mean()
    sd = cum.rolling(Z_WIN).std(ddof=1)
    return ((cum - mu) / sd).replace([np.inf, -np.inf], np.nan)


def _independent(idx: np.ndarray, h: int) -> np.ndarray:
    """Positions at least `h` bars apart -- one trade per non-overlapping forward window."""
    keep, last = [], -(10 ** 9)
    for p in idx:
        if p - last >= h:
            keep.append(p)
            last = int(p)
    return np.asarray(keep, dtype=int)


def measure(ds: DriverSet, ret: pd.DataFrame, cost_frac: float,
            shuffle: bool = False, seed: int = 0) -> list[dict]:
    """Every (horizon, threshold, side) test for one driver set. Every row is a charged trial."""
    z = residual_z(ret, ds)
    if shuffle:
        # THE NULL THIS MUST BEAT. Permuting the z-series destroys any relation to the forward
        # return while preserving its marginal distribution, its threshold crossings and the
        # sample sizes -- so anything that survives the shuffle is measuring the harness.
        v = z.to_numpy().copy()
        ok = np.isfinite(v)
        vals = v[ok]
        np.random.default_rng(seed).shuffle(vals)
        v[ok] = vals
        z = pd.Series(v, index=z.index)

    r = ret[ds.target]
    rows: list[dict] = []
    for h in HORIZONS:
        fwd = r.rolling(h).sum().shift(-h)
        d = pd.concat([z.rename("z"), fwd.rename("fwd")], axis=1).dropna()
        if len(d) < MIN_PANEL_BARS // 4:
            continue
        zv = d["z"].to_numpy()
        fv = d["fwd"].to_numpy()
        for thr in ENTRY_Z:
            hits = np.flatnonzero(np.abs(zv) >= thr)
            if hits.size < MIN_INDEPENDENT:
                continue
            keep = _independent(hits, h)
            if keep.size < MIN_INDEPENDENT:
                continue
            zk, fk = zv[keep], fv[keep]
            for side_mode in SIDE_MODES:
                sign = -np.sign(zk) if side_mode == "revert" else np.sign(zk)
                pnl = sign * fk
                sd = float(pnl.std(ddof=1))
                if not math.isfinite(sd) or sd <= 0:
                    continue
                gross = float(pnl.mean())
                se = sd / math.sqrt(pnl.size)
                pnl_all = ((-np.sign(zv[hits]) if side_mode == "revert" else np.sign(zv[hits]))
                           * fv[hits])
                sd_all = float(pnl_all.std(ddof=1))
                rows.append({
                    "cell": ds.cell, "target": ds.target, "driver_set": ds.name,
                    "drivers": list(ds.drivers), "why": ds.why,
                    "horizon_bars": h, "entry_z": thr, "side_mode": side_mode,
                    "n_overlapping": int(hits.size), "n_independent": int(keep.size),
                    "gross_per_trade": round(gross, 8),
                    "net_per_trade": round(gross - cost_frac, 8),
                    "cost_frac": round(cost_frac, 8),
                    "t_gross": round(gross / se, 3),
                    "t_naive_overlapping": round(
                        float(pnl_all.mean() / (sd_all / math.sqrt(pnl_all.size))), 3)
                    if sd_all > 0 else 0.0,
                    "clears_cost": bool(gross > cost_frac),
                })
    return rows


def _candidate(row: dict, n_tests: int, t_def: float) -> dict:
    """One proposal in the miner-discovery contract: family, params, symbol, evidence.

    `family` + `params` + a resolvable symbol is what `miner_candidate_compiler` requires for the
    EXACT_RECIPE path, and `family_inputs.resolve` rebuilds the cell from `factor_symbols`, so
    this reaches BOTH the gauntlet and the forward engine with no new wiring. The params are the
    exact arguments the measurement above used; anything else would certify a different object
    from the one that was screened.
    """
    return {
        "source": "factor_residual",
        "kind": "factor_residual",
        "symbol": row["target"],
        "family": "cross_asset_residual",
        "params": {
            "factor_symbols": list(row["drivers"]),
            "lookback": Z_WIN,
            "beta_win": BETA_WIN,
            "entry_z": float(row["entry_z"]),
            "ttl_bars": int(row["horizon_bars"]),
            "side_mode": row["side_mode"],
        },
        "mechanism": (
            f"{row['target']} regressed on {' + '.join(row['drivers'])} "
            f"({row['driver_set']}): {row['why']}. The residual is "
            f"{'faded' if row['side_mode'] == 'revert' else 'followed'} beyond "
            f"{row['entry_z']} sigma."
        ),
        "title": f"{row['cell']} residual {row['side_mode']} z>={row['entry_z']} h={row['horizon_bars']}",
        "url": "",
        "evidence": {
            "n_independent": row["n_independent"],
            "gross_per_trade": row["gross_per_trade"],
            "net_per_trade": row["net_per_trade"],
            "cost_frac": row["cost_frac"],
            "t_non_overlapping": row["t_gross"],
            "t_naive_overlapping": row["t_naive_overlapping"],
            "t_deflated_within_sweep": round(t_def, 3),
            "tests_this_sweep": n_tests,
            "screen": "causal betas, non-overlapping t, net of round trip, self-deflated",
        },
    }


def run(targets: list[str] | None = None, shuffle: bool = False,
        budget_s: float = 1500.0) -> dict:
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    have = {p.stem.removesuffix("_H1") for p in UNI.glob("*_H1.parquet")}
    sets = universe_driver_sets(meta, available=have)
    if targets:
        wanted = {t.upper() for t in targets}
        sets = [s for s in sets if s.target.upper() in wanted]

    cache: dict[str, pd.DataFrame | None] = {}
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    started = time.monotonic()
    for ds in sets:
        if time.monotonic() - started > budget_s:
            skipped[ds.cell] = "sweep budget exhausted"
            continue
        ret = panel(ds, cache)
        if ret is None:
            missing = [s for s in (ds.target, *ds.drivers) if cache.get(s) is None]
            skipped[ds.cell] = (f"no H1 bars for {', '.join(missing)}" if missing
                                else f"joint history under {MIN_PANEL_BARS} bars")
            continue
        cost = _cost_frac(ds.target, meta, cache[ds.target]["close"])
        if cost is None:
            skipped[ds.cell] = "no contract terms to price the round trip"
            continue
        rows.extend(measure(ds, ret, cost, shuffle=shuffle))

    # SELF-DEFLATION. Every row above is a test that was RUN, whatever it found, so the whole
    # count is what the best of them has to beat. Counting only the winners would be the exact
    # error the deflated Sharpe exists to correct.
    n_tests = len(rows)
    for row in rows:
        row["n_tests_sweep"] = n_tests
        row["t_deflated_sweep"] = round(deflate_t(row["t_gross"], n_tests), 3)
        row["proposed"] = bool(row["clears_cost"] and row["t_deflated_sweep"] > PROPOSE_T
                               and row["n_independent"] >= MIN_INDEPENDENT)

    proposals = [r for r in rows if r["proposed"]]
    # One proposal per cell: the whole point of deflation is that the desk pays for the search,
    # and shipping every (horizon, threshold, side) variant of one winner would smuggle the
    # search back in as candidate count. The strongest deflated t per cell is the claim.
    best: dict[str, dict] = {}
    for r in sorted(proposals, key=lambda x: -x["t_deflated_sweep"]):
        best.setdefault(r["cell"], r)

    report = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "shuffled_control": shuffle,
        "hypotheses_stated": len(sets),
        "hypotheses_measured": len({r["cell"] for r in rows}),
        "tests_run": n_tests,
        "expected_max_z": round(expected_max_z(n_tests), 3),
        "propose_threshold_t_deflated": PROPOSE_T,
        "cells_proposed": len(best),
        "skipped": skipped,
        "windows": {"beta_win": BETA_WIN, "z_win": Z_WIN, "horizons": list(HORIZONS),
                    "entry_z": list(ENTRY_Z), "side_modes": list(SIDE_MODES)},
        "proposals": sorted(best.values(), key=lambda x: -x["t_deflated_sweep"]),
        "all": rows,
    }
    # The control writes beside the real report rather than over it: a null run that clobbers the
    # live findings turns a check into data loss, and whoever reads the file next has no way to
    # tell which run produced it.
    out = REPORT.with_name(f"{REPORT.stem}_shuffled{REPORT.suffix}") if shuffle else REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    report["report_path"] = str(out)

    if best and not shuffle:
        # The shuffled control NEVER donates: its whole purpose is to be measured and discarded.
        INTEL.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")
        payload = {"source": "factor_residual", "generated_at": report["generated_at"],
                   "tests_run": n_tests,
                   "discoveries": [_candidate(r, n_tests, r["t_deflated_sweep"])
                                   for r in report["proposals"]]}
        (INTEL / f"discoveries_{stamp}.json").write_text(
            json.dumps(payload, indent=1, default=str), "utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", action="append", default=None,
                    help="restrict the sweep to these instruments (repeatable)")
    ap.add_argument("--shuffle", action="store_true",
                    help="permute the residual: the null the real run must beat")
    ap.add_argument("--budget-s", type=float, default=1500.0)
    args = ap.parse_args()

    rep = run(targets=args.target, shuffle=args.shuffle, budget_s=args.budget_s)
    tag = "  [SHUFFLED CONTROL]" if args.shuffle else ""
    print(f"FACTOR RESIDUAL SWEEP{tag}")
    print(f"  {rep['hypotheses_stated']} economic claims stated, "
          f"{rep['hypotheses_measured']} had the history to measure")
    print(f"  {rep['tests_run']} tests run -> E[max Z] = {rep['expected_max_z']}, "
          f"proposing at deflated t > {PROPOSE_T}")
    if rep["skipped"]:
        reasons: dict[str, int] = {}
        for why in rep["skipped"].values():
            key = why.split(" for ")[0]
            reasons[key] = reasons.get(key, 0) + 1
        print("  skipped: " + ", ".join(f"{k} x{v}" for k, v in sorted(reasons.items())))
    print(f"\n{'cell':34s}{'side':10s}{'h':>5}{'z':>6}{'n':>6}"
          f"{'net':>12}{'t':>8}{'t_defl':>9}")
    for r in rep["proposals"][:40]:
        print(f"{r['cell'][:33]:34s}{r['side_mode']:10s}{r['horizon_bars']:>5}"
              f"{r['entry_z']:>6.1f}{r['n_independent']:>6}{r['net_per_trade']:>12.6f}"
              f"{r['t_gross']:>8.2f}{r['t_deflated_sweep']:>9.2f}")
    if not rep["proposals"]:
        print("  (nothing cleared the round trip and its own deflation)")
    print(f"\n{rep['cells_proposed']} cell(s) proposed"
          + ("  [control: donates nothing by design]" if args.shuffle else f" -> {INTEL}"))
    print(f"written: {rep['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
