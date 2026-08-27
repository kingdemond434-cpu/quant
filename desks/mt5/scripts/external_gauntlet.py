"""Run the canonical sequential 10-gate gauntlet on external discovery survivors.

Reads survivors from external backtest, builds daily R matrix,
rejects failed economic priors at gate 1, then computes program-level PBO + SPA and the
remaining gates for candidates that can still survive. A gate-1 reject is a measured verdict,
not an untested disappearance; doing hours of downstream work after a terminal gate failure is
compute theatre and prevents fresh candidates from reaching the same machinery.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# DERIVED, NEVER HARDCODED (LAWS anti-hardcode; fixed 2026-08-26). This was the literal string
# "/home/quant/quant-platform" -- a Linux path that does not exist on the Windows desk box, so
# `sys.path.insert(str(BASE))` added nothing and every run there died on
# `ModuleNotFoundError: libs.validation` before judging a single cell. The gauntlet has to run on
# the desk box because the 4GB research box OOM-kills a full sweep, so a hardcoded path for one
# machine meant the gate could not run on the only machine with the memory to run it.
BASE = Path(__file__).resolve().parents[3]
UNI = BASE / "desks" / "mt5" / "data" / "universe"
REPORTS = BASE / "desks" / "mt5" / "reports"
DATA = BASE / "desks" / "mt5" / "data"
HYP = DATA / "hypotheses"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "desks" / "mt5"))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from research.frontier_identity import cell_id, economic_prior  # noqa: E402

from libs.validation.cpcv import CPCV  # noqa: E402
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio  # noqa: E402
from libs.validation.pbo import probability_backtest_overfitting  # noqa: E402
from libs.validation.reality_check import hansen_spa  # noqa: E402
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus  # noqa: E402

TRIALS_MULTIPLIER = 7.0
DSR_THRESHOLD = 0.95
PBO_THRESHOLD = 0.5
SPA_ALPHA = 0.05
WF_SPLITS = 4
WF_MIN_STABILITY = 0.5
COST_SCENARIO = 3.0


def costs_for(sym: str, meta: dict, mult: float = 1.0) -> Costs:
    m = meta.get(sym, {})
    spread = m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5)
    spread = 0.48 * mult if sym == "XAUUSD" else max(spread, 0.05) * mult
    return Costs(spread_per_lot=spread,
                 commission_per_lot=3.50 * mult,
                 contract_oz=m.get("contract_size", 1e5))


def daily_series(df: pd.DataFrame, sigs: list, costs: Costs) -> pd.Series:
    res = run_backtest(df, sigs, costs)
    s = pd.Series({pd.Timestamp(t.entry_time).date(): t.r_multiple for t in res.trades},
                  dtype=float)
    return s.groupby(level=0).sum()


#: One H1 frame per SYMBOL, shared by every cell on it. Each cell used to carry its own
#: `pd.read_parquet` result, so a sweep of 900+ cells held that many copies of the same handful
#: of dataframes -- gigabytes of duplicate bars on the box that also runs the MT5 terminal.
#: Sharing is not a memory/accuracy trade: the frames are read-only inputs, every cell sees
#: byte-identical bars, and skipping hundreds of redundant parquet reads makes the sweep FASTER.
#: (Re-applied 2026-08-26 after the first attempt was lost before it reached a commit -- the
#: fence now carries `_H1_CACHE` as a marker so a second loss is caught rather than repeated.)
_H1_CACHE: dict[str, object] = {}
_NATIVE_CACHE: dict[tuple[str, str], object] = {}


def _h1_for(sym: str):
    frame = _H1_CACHE.get(sym)
    if frame is None:
        pq = UNI / f"{sym}_H1.parquet"
        if not pq.exists():
            return None
        frame = families._h1(pd.read_parquet(pq))
        _H1_CACHE[sym] = frame
    return frame


def _frame_for(sym: str, family: str):
    """Load the family-authorized clock; never silently resample an M5 hypothesis to H1."""
    if family != "lvc_asia_london":
        return _h1_for(sym)
    key = (sym, "M5")
    frame = _NATIVE_CACHE.get(key)
    if frame is None:
        pq = UNI / f"{sym}_M5.parquet"
        if not pq.exists():
            return None
        frame = pd.read_parquet(pq).sort_index()
        if not isinstance(frame.index, pd.DatetimeIndex):
            return None
        frame.index = (frame.index.tz_localize("UTC") if frame.index.tz is None
                       else frame.index.tz_convert("UTC"))
        frame = frame[~frame.index.duplicated(keep="last")]
        _NATIVE_CACHE[key] = frame
    return frame


def build_cell(sym: str, family: str, params: dict, meta: dict,
               h1_override: pd.DataFrame | None = None):
    """Build a Cell from external survivor spec.

    `h1_override` lets a caller supply bars it has already vetted instead of whatever parquet
    happens to be on disk. `external_shadow` needs exactly that: it fetches with
    `prefer_promotion_authority=True`, so its forward clock must run on the source that CARRIES
    that authority -- rebuilding from disk would run the clock on a different tape than the one
    the caller checked, and nothing downstream could tell.

    This parameter was added on 2026-08-26 (6098dcfd) and dropped again by the cache refactor
    that introduced `_frame_for`, which broke `external_shadow` with a TypeError. Because that
    organ is scheduled by NOTHING, the break was silent and the entire `overnight_gap_decay`
    family -- the desk's only certificates outside session_range_breakout, against a
    largest_family_share of 0.87 -- never started a forward clock at all.
    """
    if h1_override is not None:
        # NEVER silently resample: `_frame_for` exists to keep an M5-native hypothesis off an H1
        # clock, and an override must not become the hole in that rule. A caller handing H1 bars
        # for an M5 family is a wiring error, and returning None reports it as one.
        if family == "lvc_asia_london":
            return None
        h1 = families._h1(h1_override)
    else:
        h1 = _frame_for(sym, family)
    if h1 is None:
        return None
    # THE GAUNTLET MUST REACH EVERY FAMILY, not just the breakout module. Looking only in
    # `families` meant the 14 orthogonal generators were unreachable from the one door that grants
    # certificates -- so a carry or positioning edge could be written, tested by hand, and still
    # never certify. That is the same defect as having no generator at all, one layer further in.
    fn = getattr(families, f"family_{family}", None)
    if fn is None:
        try:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        except ImportError:
            fn = None
    if fn is None:
        return None
    # Reconstruct runtime-only data from the serializable candidate identity. Previously the
    # orthogonal sweep persisted `{}` for every peer/tape/macro/COT family, and discovered
    # cross-asset features were rebuilt without `extra`; both paths therefore produced zero
    # signals after apparently successful discovery. One producer -> one exact executable.
    call_params = dict(params or {})
    try:
        from research import orthogonal_sweep as inputs

        if family == "carry":
            call_params.pop("input_symbol", None)
            call_params["symbol"] = sym
        elif family in {"relative_value", "correlation_regime"}:
            peer_symbol = call_params.pop("peer_symbol", None)
            call_params["peer"] = inputs._bars(str(peer_symbol)) if peer_symbol else None
        elif family == "cross_asset_residual":
            factor_symbols = call_params.pop("factor_symbols", [])
            call_params["factors"] = [d for d in (inputs._bars(str(s)) for s in factor_symbols)
                                      if d is not None]
        elif family in {"liquidity_regime", "orderflow_imbalance"}:
            call_params.pop("input_source", None)
            spread, flow = inputs._tape_series(sym, h1.index)
            call_params["spread_series" if family == "liquidity_regime" else "flow"] = (
                spread if family == "liquidity_regime" else flow
            )
        elif family == "macro_conditional":
            call_params.pop("input_source", None)
            call_params["macro"] = inputs._macro_series(h1.index)
        elif family == "cot_positioning":
            call_params.pop("input_source", None)
            call_params["cot"] = inputs._cot_frame(sym)
        elif family == "event_reaction":
            call_params.pop("input_source", None)
            call_params["events"] = inputs._event_index()
        elif family == "discovered":
            from research.edge_search import resolve_inputs

            all_symbols = sorted(p.stem.removesuffix("_H1") for p in UNI.glob("*_H1.parquet"))
            call_params["extra"] = resolve_inputs(sym, h1.index, all_symbols)
    except Exception as exc:
        print(f"  INPUT-FAIL {sym}.{family}: {type(exc).__name__}: {exc}")
        return None

    side = 1  # both sides tested externally; use LONG default
    try:
        sigs = fn(h1, side=side, **call_params)
    except TypeError:
        try:
            sigs = fn(h1, **call_params)
        except Exception:
            return None
    costs = costs_for(sym, meta)
    return {"sym": sym, "family": family, "params": params, "df": h1, "sigs": sigs, "costs": costs}


def partition_at_economic_prior(specs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Apply gate 1 before constructing signals and return eligible specs plus exact rejects."""
    eligible: list[dict] = []
    rejected: list[dict] = []
    for spec in specs:
        stage = economic_prior(spec)
        if stage["passed"]:
            eligible.append(spec)
            continue
        rejected.append({
            "cell": cell_id(spec),
            "sym": spec["sym"],
            "family": spec["family"],
            "days": 0,
            "passed": False,
            "terminal_gate": "economic_prior",
            "stages": {"economic_prior": stage},
            "downstream_status": "NOT_RUN_TERMINAL_GATE_1_REJECT",
        })
    return eligible, rejected




# ------------------------------------------------------------------ hourly-sweep series cache
#: The sweep is HOURLY but a cell's daily series can only change when a trading DAY completes.
#: Recomputing 3,000+ signal replays and backtests every hour therefore buys nothing 23 runs out
#: of 24 -- measured: a full docket sweep took the better part of an hour, all of it recomputing
#: byte-identical series. Each cell's 1x and 3x-cost daily series are cached keyed by
#: (cell identity, params, symbol, LAST COMPLETE DAY): a new candidate computes once, everything
#: else loads. This is pure compute caching -- same series, same matrix, same gates.
#:
#: WHY EVERY SERIES ENDS AT THE LAST COMPLETE DAY (fresh and cached alike). The gate matrix
#: aligns columns BY LENGTH from the end, not by date-join, so mixing a series computed at 01:00
#: with one computed at 14:00 would silently compare yesterday's row of one cell against today's
#: partial row of another -- cross-sectional PBO/SPA on misaligned dates. Dropping the partial
#: day makes every column end on the same complete day regardless of computation hour; a partial
#: day was never a day's return to begin with.
CACHE_DIR = REPORTS / "gauntlet_cache"


def _cache_key(sym: str, family: str, params: dict, last_day: str) -> str:
    import hashlib
    blob = json.dumps({"s": sym, "f": family, "p": params, "d": last_day},
                      sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def _series_trim_partial(ds, last_day):
    """Drop the current partial day so every column ends on the same COMPLETE day."""
    if ds is None or len(ds) == 0:
        return ds
    try:
        return ds[ds.index < last_day]
    except Exception:
        return ds


def cache_load(key: str):
    f = CACHE_DIR / f"{key}.npz"
    if not f.exists():
        return None
    try:
        import numpy as _np
        z = _np.load(f, allow_pickle=False)
        idx = pd.to_datetime(z["dates"])
        return (pd.Series(z["v1"], index=idx), pd.Series(z["v3"], index=idx))
    except Exception:
        return None


_CACHE_SAVE_WARNED = [False]


def cache_save(key: str, ds1, ds3) -> None:
    """Persist one cell's series pair. A save failure is REPORTED once, never swallowed.

    The first deployment produced ZERO files on the desk box and nobody knew: every save failed
    inside a bare `except: pass`, the warm sweep ran exactly as slow as the cold one (12.2 vs
    12.4 min), and the only symptom was a missing speedup -- which reads as "the box is slow",
    not "the cache is broken". The loud path then caught the actual bug within one run: some
    families' daily series carry plain datetime.date objects, not a DatetimeIndex, and
    astype("int64") on those raises TypeError, so pd.to_datetime normalizes first.
    """
    try:
        import numpy as _np
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        common = ds1.index.intersection(ds3.index)
        _np.savez_compressed(CACHE_DIR / f"{key}.npz",
                             dates=pd.to_datetime(common).astype("int64").to_numpy(),
                             v1=ds1.reindex(common).to_numpy(float),
                             v3=ds3.reindex(common).to_numpy(float))
    except Exception as exc:
        if not _CACHE_SAVE_WARNED[0]:
            _CACHE_SAVE_WARNED[0] = True
            print(f"  CACHE SAVE FAILING ({type(exc).__name__}: {exc}) -- sweeps will run at "
                  f"cold speed until this is fixed; reporting once, not per cell")

def run_gauntlet(cells: list, hunt_name: str, meta: dict) -> dict:
    """Run full 10-gate gauntlet on a list of cells."""
    print(f"\n=== GAUNTLET: {hunt_name} ({len(cells)} cells) ===")

    # Build daily series
    daily = []
    hits = 0
    for c in cells:
        try:
            if c.get("_cached_ds") is not None:
                daily.append(c["_cached_ds"])
                hits += 1
                continue
            last_day = c.get("_last_day")
            ds = _series_trim_partial(daily_series(c["df"], c["sigs"], c["costs"]), last_day)
            c["_fresh_ds"] = ds
            daily.append(ds)
        except Exception as e:
            print(f"  FAIL {c['sym']}.{c['family']}: {e}")
            daily.append(None)
    if hits:
        print(f"  series cache: {hits}/{len(cells)} cell(s) loaded (unchanged data-day); "
              f"{len(cells) - hits} computed fresh")

    # Build matrix from valid series
    # WHERE CELLS DIE, BY FAMILY. A cell that builds but yields fewer than 60 trading days has
    # no series the gates can judge, and until now it vanished silently -- 575 `discovered` cells
    # were built, dropped here, and reported nowhere, so the sweep looked like it had simply not
    # found them. A drop is a measurement and belongs in the log with its reason (L1.28a).
    _drop: dict[str, dict[str, int]] = {}
    for _i, _d in enumerate(daily):
        _fam = str(cells[_i].get("family", "?"))
        _row = _drop.setdefault(_fam, {"built": 0, "no_series": 0, "too_few_days": 0, "kept": 0})
        _row["built"] += 1
        if _d is None:
            _row["no_series"] += 1
        elif len(_d) < 60:
            _row["too_few_days"] += 1
        else:
            _row["kept"] += 1
    for _fam, _row in sorted(_drop.items(), key=lambda kv: -kv[1]["built"]):
        if _row["kept"] != _row["built"]:
            print(f"  cells {_fam}: built={_row['built']} kept={_row['kept']} "
                  f"no_series={_row['no_series']} under_60_days={_row['too_few_days']}")

    valid = [(i, d) for i, d in enumerate(daily) if d is not None and len(d) >= 60]
    if not valid:
        print("  NO cells with >= 60 days")
        return {"hunt": hunt_name, "error": "no valid cells", "verdicts": []}

    cols = [d.to_numpy(float) for _, d in valid]
    min_len = min(len(a) for a in cols)
    matrix = np.column_stack([a[-min_len:] for a in cols])

    # Program-level tests
    # THE CANONICAL TRIAL BASIS, AND NOTHING ELSE (principal 2026-08-26: "we don't count trials
    # of deflation, we don't use any harsh gates -- it's direct discovery, backtest, 10 gates,
    # certification, forward, then live"). The sealed attestation DEFINES this basis and it is not
    # mine to substitute. An earlier revision raised n_trials to the width a search declared
    # (43,512 instead of 378), which made `deflated_sharpe` dramatically harsher -- the same
    # unsanctioned bar I had just deleted from the searcher, moved INSIDE the gate where it was
    # less visible. The ten gates run exactly as defined.
    n_trials = max(2, math.ceil(matrix.shape[1] * TRIALS_MULTIPLIER))
    sharpes = np.array([sharpe_ratio(matrix[:, k]) for k in range(matrix.shape[1])])
    sh_var = float(sharpes.var(ddof=1)) if len(sharpes) > 1 else 0.0

    print(f"  Matrix: {matrix.shape}, n_trials={n_trials}")
    t0 = time.time()

    if matrix.shape[1] < 2:
        # PBO and SPA are program-level relative-performance tests. One surviving series is not
        # evidence that it passes them, but it is also not an exception that should abort the
        # entire hourly certifier. Record the two gates as conservative measured failures so the
        # candidate remains visible and the authority file is still published intact.
        pbo_val, pbo_ok = 1.0, False
        spa_p, spa_ok = 1.0, False
        print("  PBO: 1.0000 (FAIL: requires >=2 strategies)")
        print("  SPA: p=1.0000 (FAIL: requires >=2 strategies)")
    else:
        pbo = probability_backtest_overfitting(matrix)
        pbo_val = float(pbo.pbo)
        pbo_ok = pbo_val <= PBO_THRESHOLD
        print(f"  PBO: {pbo_val:.4f} ({'PASS' if pbo_ok else 'FAIL'})")

        spa = hansen_spa(matrix)
        spa_p = float(spa.p_value)
        spa_ok = spa_p < SPA_ALPHA
        print(f"  SPA: p={spa_p:.4f} ({'PASS' if spa_ok else 'FAIL'})")

    # 3x cost series
    daily_x3 = []
    for c in cells:
        try:
            if c.get("_cached_ds3") is not None:
                daily_x3.append(c["_cached_ds3"])
                continue
            costs3 = costs_for(c["sym"], meta, mult=COST_SCENARIO)
            ds3 = _series_trim_partial(daily_series(c["df"], c["sigs"], costs3),
                                       c.get("_last_day"))
            daily_x3.append(ds3)
            if c.get("_fresh_ds") is not None and ds3 is not None and c.get("_ckey"):
                cache_save(c["_ckey"], c["_fresh_ds"], ds3)
        except Exception:
            daily_x3.append(None)

    # Per-cell verdicts
    verdicts = []
    for _idx, (orig_i, ds) in enumerate(valid):
        c = cells[orig_i]
        arr = ds.to_numpy(float)
        cid = cell_id(c)

        # In-sample
        sr = sharpe_ratio(arr)
        stages = {
            "economic_prior": economic_prior(c),
            "in_sample_screen": {"passed": bool(sr > 0.0), "sharpe": round(float(sr), 4)},
        }

        # Deflated Sharpe
        dsr = deflated_sharpe_ratio(arr, n_trials=n_trials,
                                    variance_of_sharpes=sh_var, threshold=DSR_THRESHOLD)
        stages["deflated_sharpe"] = {
            "passed": bool(dsr.passed), "dsr": round(float(dsr.dsr), 4),
            "sr0": round(float(dsr.sr0_threshold), 4), "n_trials": n_trials
        }

        # PBO + SPA (program-level)
        stages["pbo"] = {"passed": pbo_ok, "pbo": round(pbo_val, 4)}
        stages["reality_check_spa"] = {"passed": spa_ok, "p_value": round(spa_p, 4)}

        # CPCV
        cpcv = CPCV(n_groups=6, n_test_groups=2)
        oos = []
        for split in cpcv.split(len(arr)):
            te = np.asarray(split.test)
            if len(te) >= 30:
                oos.append(sharpe_ratio(arr[te]))
        cpcv_mean = float(np.mean(oos)) if oos else 0.0
        stages["cpcv"] = {"passed": bool(cpcv_mean > 0.0),
                          "mean_oos_sharpe": round(cpcv_mean, 4), "folds": len(oos)}

        # Walk Forward
        try:
            wf = WalkForwardEngine().evaluate(arr, n_splits=WF_SPLITS,
                                              test_size=max(20, len(arr) // 6),
                                              min_oos_sharpe=0.0,
                                              min_stability=WF_MIN_STABILITY)
            wf_status = wf.status
            wf_oos = float(wf.oos_sharpe)
            wf_stab = float(wf.stability)
        except Exception:
            wf_status, wf_oos, wf_stab = "TOO_SHORT", float("-inf"), 0.0
        stages["walk_forward"] = {
            "passed": bool(wf_status is WalkForwardStatus.PASSED),
            "oos_sharpe": round(wf_oos, 4), "stability": round(wf_stab, 4)
        }

        # Stress costs (3x)
        x3_ds = daily_x3[orig_i]
        exp3 = float(x3_ds.to_numpy(float).mean()) if x3_ds is not None and len(x3_ds) > 0 else 0.0
        stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}

        # Lockbox
        stages["lockbox"] = {"passed": bool(wf_oos >= 0.0),
                             "lockbox_sharpe": round(wf_oos, 4)}

        # Expected Value
        ev = float(arr.mean())
        stages["expected_value"] = {"passed": bool(ev > 0.0), "ev": round(ev, 4)}

        passed = all(s["passed"] for s in stages.values())
        verdicts.append({
            "cell": cid, "sym": c["sym"], "family": c["family"],
            "days": len(arr), "passed": passed, "stages": stages
        })

    elapsed = time.time() - t0
    n_pass = sum(1 for v in verdicts if v.get("passed"))
    gate_fails = {}
    for v in verdicts:
        for name, s in v.get("stages", {}).items():
            if not s["passed"]:
                gate_fails[name] = gate_fails.get(name, 0) + 1

    print(f"\n  RESULT: {n_pass}/{len(verdicts)} pass all 10 gates ({elapsed:.0f}s)")
    if gate_fails:
        print(f"  Gate failures: {gate_fails}")

    for v in verdicts:
        status = "PASS" if v["passed"] else "FAIL"
        print(f"  {status} {v['cell']:<50} n={v['days']}")
        if not v["passed"]:
            for name, s in v["stages"].items():
                if not s["passed"]:
                    print(f"         FAIL {name}: {s}")

    return {
        "hunt": hunt_name,
        "n_cells": len(cells),
        "n_trials": n_trials,
        "program_level": {"pbo": round(pbo_val, 4), "spa_p": round(spa_p, 4)},
        "survivors_passing_all": n_pass,
        "gate_fails": gate_fails,
        "verdicts": verdicts,
        "swept_at": datetime.now(UTC).isoformat(),
    }


def main():
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))

    # Load external backtest survivors
    surv_file = HYP / "external_survivors.json"
    if not surv_file.exists():
        print("No external survivors found")
        return
    survivors = json.loads(surv_file.read_text("utf-8"))
    print(f"Loaded {len(survivors)} external survivors")
    # EMPTY INPUT IS A HALT, NOT A SWEEP (2026-08-26, measured). The hourly merge briefly wrote
    # a 0-row input; this gauntlet then ran "normally" on nothing and rewrote the AUTHORITY file
    # to n=0 -- wiping 21 certificates with exit code 0. Zero candidates means there is nothing
    # to judge, and a judge with an empty docket must not touch the records of past verdicts.
    if not survivors:
        print("HALT: 0 candidates in the input -- nothing to judge. Refusing to write any "
              "report or touch UNIVERSAL_SURVIVORS.json; an empty docket does not revoke past "
              "verdicts.")
        return

    # Group by unique (sym, family, params) combos
    cells = {}
    for h in survivors:
        sym = h.get("symbol")
        fam = h.get("family")
        params = h.get("params", {})
        if not sym or not fam:
            continue
        key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"
        if key not in cells:
            cells[key] = {
                "sym": sym,
                "family": fam,
                "params": params,
                "mechanism_status": h.get("mechanism_status"),
                "mechanism_note": h.get("mechanism_note"),
            }

    print(f"Unique cells to evaluate: {len(cells)}")
    families_submitted: dict[str, int] = {}
    for spec in cells.values():
        fam = str(spec.get("family") or "UNKNOWN")
        families_submitted[fam] = families_submitted.get(fam, 0) + 1
    print(f"Submitted families: {families_submitted}")

    # GATES ARE SEQUENTIAL. A statistical pattern with no falsifiable economic mechanism fails
    # the first canonical gate. Before this partition, 2,760 such rows consumed days of signal
    # construction, CPCV and walk-forward work despite having zero path to a certificate. Record
    # each exact reject, but reserve downstream compute for candidates still capable of passing.
    eligible_specs, prior_rejections = partition_at_economic_prior(list(cells.values()))
    print(f"Economic prior: {len(eligible_specs)} advance; {len(prior_rejections)} terminal reject")

    # Build cell objects -- CACHE FIRST. A cell whose (identity, params, last complete data-day)
    # was already computed loads its 1x and 3x daily series and skips signal generation AND both
    # backtests entirely; only genuinely new candidates, or a new trading day, pay for compute.
    # This is what makes an hourly sweep of a 3,000+ docket take minutes instead of the hour.
    cell_objs = []
    cache_hits = 0
    # Yesterday's keys die with yesterday's data-day; prune so the cache never grows unbounded.
    try:
        import time as _t
        for _f in CACHE_DIR.glob("*.npz"):
            if _t.time() - _f.stat().st_mtime > 3 * 86400:
                _f.unlink(missing_ok=True)
    except OSError:
        pass
    for spec in eligible_specs:
        key = f"{spec['sym']}.{spec['family']}.{json.dumps(spec['params'], sort_keys=True)}"
        frame = _h1_for(spec["sym"])
        if frame is None or len(frame) == 0:
            print(f"  SKIP {key}: parquet missing")
            continue
        last_day = frame.index[-1].normalize()
        ckey = _cache_key(spec["sym"], spec["family"], spec["params"] or {}, str(last_day.date()))
        cached = cache_load(ckey)
        if cached is not None:
            ds1, ds3 = cached
            cell_objs.append({
                "sym": spec["sym"], "family": spec["family"], "params": spec["params"],
                "df": None, "sigs": None, "costs": None,
                "_cached_ds": ds1, "_cached_ds3": ds3, "_ckey": ckey, "_last_day": last_day,
                "mechanism_status": spec.get("mechanism_status"),
                "mechanism_note": spec.get("mechanism_note"),
            })
            cache_hits += 1
            continue
        obj = build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if obj:
            obj["mechanism_status"] = spec.get("mechanism_status")
            obj["mechanism_note"] = spec.get("mechanism_note")
            obj["_ckey"], obj["_last_day"] = ckey, last_day
            cell_objs.append(obj)
        else:
            print(f"  SKIP {key}: parquet missing or build failed")
    if cache_hits:
        print(f"Cell cache: {cache_hits}/{len(eligible_specs)} loaded (same data-day), "
              f"{len(eligible_specs) - cache_hits} to compute")

    # Run the remaining gates, or still emit the complete gate-1 rejection ledger when none can
    # advance. A no-mechanism discovery batch is a valid negative result, not a missing report.
    if cell_objs:
        result = run_gauntlet(cell_objs, "external_discoveries", meta)
    else:
        print("No candidates advanced beyond the economic-prior gate")
        result = {
            "hunt": "external_discoveries",
            "n_cells": 0,
            "n_trials": 0,
            "program_level": {"status": "NOT_RUN_NO_GATE_1_ELIGIBLE_CELLS"},
            "survivors_passing_all": 0,
            "gate_fails": {},
            "verdicts": [],
            "swept_at": datetime.now(UTC).isoformat(),
        }
    result["n_cells_discovered"] = len(cells)
    result["n_cells_advanced_beyond_economic_prior"] = len(cell_objs)
    result["n_cells_rejected_at_economic_prior"] = len(prior_rejections)
    result["verdicts"] = prior_rejections + list(result.get("verdicts", []))
    result.setdefault("gate_fails", {})["economic_prior"] = (
        int(result.get("gate_fails", {}).get("economic_prior", 0)) + len(prior_rejections)
    )

    # Save
    out = REPORTS / "universal_gates_external.json"
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to {out}")

    # Update UNIVERSAL_SURVIVORS.json -- FULL AUTHORITY OR NOTHING. An earlier revision of this
    # block wrote certificates without the top-level `gate_policy` attestation and without a
    # per-survivor `shadow_spec`; `shadow_admission.is_exact_policy` fails closed on the missing
    # attestation, so one run of this script would have stripped promotion authority from EVERY
    # certificate in the file while printing "Updated". A certifier that demotes what it did not
    # examine is the certifier-wipe defect again, one layer up.
    sys.path.insert(0, str(BASE / "desks" / "mt5" / "research"))
    from gate_policy import ATTESTATION

    surv_path = REPORTS / "UNIVERSAL_SURVIVORS.json"
    survivors_all, old_doc = {}, {}
    if surv_path.exists():
        try:
            old_doc = json.loads(surv_path.read_text("utf-8"))
            survivors_all = old_doc.get("survivors", {})
        except Exception:
            pass
    n_before = len(survivors_all)

    WINDOWS_KNOWN = {
        "asia": {"range_start": 7},
        "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13},
        "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14},
        "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17},
    }

    def _selector(params: dict) -> str | None:
        """Map a cell's params to the ONE forward engine's window name -- or None, visibly.

        A certificate whose selector cannot be named cannot be enrolled, and an un-enrollable
        certificate trips the same-day fence (CERTIFIED-NOT-ENROLLED) rather than silently
        running under guessed hours. The default family session (range_start=7) IS "asia"."""
        if params.get("window") in WINDOWS_KNOWN:
            return params["window"]
        keys = {k: params[k] for k in ("range_start", "range_end", "signal_at") if k in params}
        if not keys or keys == {"range_start": 7}:
            return "asia"
        for name, w in WINDOWS_KNOWN.items():
            if all(w.get(k) == v for k, v in keys.items()):
                return name
        return None

    _params_by_cell = {cell_id(c): dict(c.get("params") or {}) for c in cell_objs}
    for v in result.get("verdicts", []):
        if not v.get("passed"):
            continue
        key = f"external.{v['cell']}"
        # EXACT MATCH ON THE CELL ID, not a prefix. `f"{sym}.{family}" in cell` matched the FIRST
        # cell sharing that prefix, so every CADJPY certificate inherited rr=1.5 from whichever
        # variant was built first -- wrong params on 14 of 15 certificates, which is worse than
        # none. The cid formula in run_gauntlet encodes rr and wait_bars, so it is a unique key.
        params = _params_by_cell.get(v["cell"], {})
        sel = _selector(params or {})
        row = {
            "hunt": "external_discoveries",
            "cell": v["cell"],
            "sym": v["sym"],
            "days": v["days"],
            "gates": v["stages"],
            "gated_at": datetime.now(UTC).isoformat(),
        }
        if sel is not None:
            # PARAMS ARE PART OF THE IDENTITY. Without them the spec says only "XAUUSD asia",
            # so five separately-gauntleted parameterizations collapse to ONE runnable spec and
            # the forward engine runs its own default for all of them -- four certificates
            # describing strategies that are never forward-tested. The two-stage law requires
            # that the thing which passed the gauntlet IS the thing that goes forward, and that
            # identity is the params, not the session label.
            row["shadow_spec"] = {"symbol": v["sym"], "selector": sel,
                                  "family": v.get("family", "session_range_breakout"),
                                  "is_universe": True, "hunt": "external_discoveries",
                                  "condition": None, "params": dict(params or {})}
        else:
            print(f"  NO-SPEC {key}: params {params} match no known window; certificate "
                  f"written WITHOUT shadow_spec -- it cannot enrol until the selector is wired")
        survivors_all[key] = row

    # NEVER SHRINK (2026-08-26, the certifier wipe): merging can only grow this file; a sweep
    # that certified nothing preserves what stands, because re-running a gauntlet is not
    # revoking a pass.
    if len(survivors_all) < n_before:
        print(f"REFUSING to write: merge would shrink {n_before} -> {len(survivors_all)}")
        return
    # NEVER WRITE EMPTY (2026-08-27): a zeroed input file sails through the shrink check as
    # 0 -> 0, and this run then re-publishes the wipe with its own signature -- observed on the
    # desk box, healed only because the moneypath fence restored canon between runs. An empty
    # survivors file is never a verdict; if nothing has ever certified there is nothing to write.
    if not survivors_all:
        print("REFUSING to write an EMPTY canon: 0 survivors is a missing input, not a verdict.")
        return

    doc = dict(old_doc)
    doc.update({
        "n": len(survivors_all),
        "gate_policy": ATTESTATION,
        "survivors": survivors_all,
        "note": "UNIVERSAL 10-GATE PASS ONLY.",
        "swept_at": datetime.now(UTC).isoformat(),
    })
    surv_path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"Updated UNIVERSAL_SURVIVORS.json: {len(survivors_all)} total "
          f"({len(survivors_all) - n_before:+d})")

    # FILE THE CLAIM. Every other certified producer writes SURVIVORS_LEDGER.json alongside the
    # survivor file (universal_gate, survivor_publication, ug_remote); this one never did, and it
    # is the producer of the `external.*` lane. Measured 2026-08-27: 23 survivors, 1 claim -- 22
    # `external.*` passes with no ledger row, the ledger two days stale while the survivor file
    # was rewritten that morning. desks/mt5/CLAUDE.md makes this ledger a binding session-start
    # read ("count them and act"), so a session obeying it saw ONE pipeline claim while
    # twenty-three certificates stood and seventeen were already on forward clocks. A survivor
    # invisible to the ledger is a survivor nobody is required to action.
    # Merge, never replace: another producer may have published while this sweep was running,
    # exactly as the survivor merge above already guards.
    ledger_path = REPORTS / "SURVIVORS_LEDGER.json"
    claims: dict = {}
    if ledger_path.exists():
        try:
            loaded = json.loads(ledger_path.read_text("utf-8")).get("claims")
            claims = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            # A torn ledger must not be silently replaced by this run's rows alone -- that would
            # erase every other lane's claims. Report and leave it for repair.
            print("REFUSING to file claims: SURVIVORS_LEDGER.json exists but is unreadable")
            return
    now_iso = datetime.now(UTC).isoformat()
    for k, v in survivors_all.items():
        claims[k] = {**v, "status": "UNIVERSAL", "updated_at": now_iso}
    ledger_path.write_text(json.dumps({"n": len(claims), "claims": claims},
                                      indent=2, default=str), encoding="utf-8")
    print(f"SURVIVORS_LEDGER.json: {len(claims)} claim(s)")


if __name__ == "__main__":
    main()
