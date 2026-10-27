"""Does each allocator input beat the plain solve OUT OF SAMPLE? (2026-10-27)

    "and allocator maximising fr maximum growth opportunities like instituitions cross asset
     tradings maccros allocations based on macro n geopolitics max coverage of news everything
     breadth n bayesian hhm garch everything right"
    "constantly maximise all so they have highest chanc of profitabilities n beatings"
                                                                  -- zuck, 2026-10-27 21:48Z

WHAT WAS MISSING. The HMM regime mix (`pf_allocator.regime_state`) and the macro kernel tilt
(`SleeveEvidence.macro_w`) both move money, and neither was ever compared with the allocator
WITHOUT it on outcomes it had not seen. `STATE_ADMISSION` removes a state dimension once it is
measured worse; nothing required an input to be measured BETTER. This module is that test.

THE TEST. Walk forward over the desk's own daily matrix. At each rebalance day t, every arm
re-solves the allocator on the history up to t only -- the plain arm with no regime mix and no
macro tilt, each input arm with exactly one of them read AS OF t (`regime_state(asof=)`,
`macro_state.kernel_weights(asof=)`) -- and the book it chose is held over the next `HORIZON`
days of REALIZED sleeve returns. The score is realized log growth, log(1 + sum_i h_i r_i) summed
over the holding window, and the verdict is a paired test of arm minus plain over
non-overlapping windows. Same worlds seed, same caps, same bounds on every arm: the input is the
only difference.

WHAT THE VERDICT MEANS. PROMOTE: the input added realized growth at |t| >= `T_DECIDE` over at
least `MIN_PERIODS` windows. DEMOTE: it cost growth at the same bar. UNPROVEN otherwise. The bar
is a constant here and never moves to let an input pass. The report has no authority of its own:
the allocator reads it only through `verdict_for` once that wiring is audited.

LIMITS, SAID ONCE. A macro series with no ALFRED vintage is the current vintage, so its later
revisions leak into the replay; the report names the vintage. The matrix is the desk's own
evidence (backtest, forward and live rows aligned), not live fills.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, optimise  # noqa: E402

OUT = BASE / "reports" / "INPUT_ABLATION.json"
CACHE = BASE / "data" / "pf_allocator_cache" / "input_ablation_cache.json"

#: Days each chosen book is held before it is scored. DERIVATION: the allocator's own regime
#: forecast horizon is 5 trading days (`pf_allocator.REGIME_FORECAST_H`), the horizon the regime
#: mix is claimed to be right about; a shorter hold would score a claim it never made.
HORIZON = 5
#: Rebalance days are `HORIZON` apart, so holding windows never overlap and the paired
#: differences are independent draws for the t-statistic (the paired design's assumption).
STEP = HORIZON
#: Days of history an arm must have before its first solve. DERIVATION: `regime_state` refuses
#: to fit on fewer than 250 daily closes; 250 is used for every arm so all start on one day.
WARMUP = 250
#: Minimum non-overlapping windows before any verdict. DERIVATION (power): a paired test at
#: |t| >= 2 has power 0.8 against a standardised effect d when n*d^2 >= (2 + 0.84)^2 = 8.07;
#: n = 26 detects d = 0.56, half a year of weekly windows.
MIN_PERIODS = 26
#: Verdict bar on the paired t-statistic, aligned with `libs.regime.state_admission` ADMIT_T
#: (2.0): the same significance as the only other out-of-sample gate on this desk.
T_DECIDE = 2.0
#: World population for each replay solve: the allocator's own fast-clock population
#: (`pf_allocator.run`, mode fast: 128 worlds x 256 rows), per the cheapest solve the desk trusts.
N_WORLDS = 128
N_ROWS = 256
#: The plain solve and one arm per input under test; every arm solves under the same
#: `heat_policy.HEAT_TARGET` cap and per-sleeve bounds, so only the input differs.
ARMS = ("plain", "regime", "macro")
#: Windows the daily run keeps: the newest 52, a year of weekly windows, twice `MIN_PERIODS` so a
#: verdict can stand on one half and be re-checked on the other.
MAX_WINDOWS = 52
#: Wall-clock seconds the daily-cycle step may spend solving NEW windows; the rest wait for the
#: next day's schedule (each solved window is cached, so the backlog only shrinks). DERIVATION:
#: 1800 s is half the 3600 s hourly cadence, so one day's step never holds the chain an hour.
BUDGET_S = 1800.0
#: Bump when the arm definitions or the score change; cached windows from another version are
#: re-solved, never reused.
VERSION = 1


@dataclasses.dataclass(frozen=True)
class ArmInputs:
    """What one arm adds to the plain solve at one rebalance day."""
    regime_labels: tuple[str, ...] = ()
    regime_probs: tuple[tuple[str, float], ...] = ()
    macro_w: Mapping[str, np.ndarray] | None = None       # sleeve name -> weights over its rows


def realized_growth(heat: Mapping[str, float], fwd: pd.DataFrame) -> float:
    """sum_d log(1 + sum_i h_i r_{i,d}) over the holding window; -inf on ruin."""
    if fwd.empty:
        return 0.0
    h = np.array([float(heat.get(str(c), 0.0)) for c in fwd.columns])
    port = np.nan_to_num(fwd.to_numpy(dtype=float), nan=0.0) @ h
    if np.any(port <= -1.0):
        return float("-inf")
    return float(np.log1p(port).sum())


def paired_verdict(diffs: Sequence[float]) -> dict[str, Any]:
    """Arm minus plain, one value per non-overlapping window."""
    d = np.array([x for x in diffs if math.isfinite(x)], dtype=float)
    n = int(d.size)
    out: dict[str, Any] = {"n_periods": n, "min_periods": MIN_PERIODS, "t_decide": T_DECIDE}
    if n < 2:
        out.update(verdict="UNPROVEN", why=f"{n} window(s); {MIN_PERIODS} needed")
        return out
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    t = mean / (sd / math.sqrt(n)) if sd > 0 else (math.inf if mean > 0 else
                                                     -math.inf if mean < 0 else 0.0)
    out.update(mean_log_growth_diff=round(mean, 8), sd=round(sd, 8),
               t=round(t, 3) if math.isfinite(t) else t,
               total_log_growth_diff=round(float(d.sum()), 8))
    if n < MIN_PERIODS:
        out.update(verdict="UNPROVEN", why=f"{n} window(s); {MIN_PERIODS} needed")
    elif t >= T_DECIDE:
        out.update(verdict="PROMOTE", why=f"beats the plain solve out of sample at t={t:.2f}")
    elif t <= -T_DECIDE:
        out.update(verdict="DEMOTE", why=f"loses to the plain solve out of sample at t={t:.2f}")
    else:
        out.update(verdict="UNPROVEN", why=f"|t|={abs(t):.2f} < {T_DECIDE}")
    return out


def _digest(*parts: Any) -> str:
    h = hashlib.sha256(f"input-ablation-v{VERSION}".encode())
    for p in parts:
        if isinstance(p, np.ndarray):
            a = np.ascontiguousarray(p)
            h.update(str((a.dtype.str, a.shape)).encode())
            h.update(a.tobytes())
        else:
            h.update(json.dumps(p, sort_keys=True, default=str).encode())
    return h.hexdigest()


def ablate(daily: pd.DataFrame, ev: Sequence[SleeveEvidence],
           arm_inputs: Callable[[str, str, pd.DataFrame], ArmInputs], *,
           solve: Callable[[list[SleeveEvidence], WorldConfig], Mapping[str, float]],
           arms: Sequence[str] = ARMS, horizon: int = HORIZON, step: int = STEP,
           warmup: int = WARMUP, max_windows: int | None = None,
           cache: dict[str, Any] | None = None, seed: int = 0,
           data_key: str = "", deadline: float | None = None) -> dict[str, Any]:
    """Walk-forward ablation. `arm_inputs(arm, asof_day, history)` returns what that arm adds,
    built from `history` (rows up to and including `asof_day`) only; `solve` is the allocator.
    `cache` maps a window's digest to its stored books, so a daily run re-solves only new days;
    `data_key` names the version of everything the arms read besides `daily` (the regime bars,
    the macro archive), so a revised input re-solves every window. Past `deadline` (epoch
    seconds) no new window is solved; the windows solved so far are scored and cached.
    """
    cache = {} if cache is None else cache
    idx = [str(d)[:10] for d in daily.index]
    by_name = {e.name: e for e in ev if e.name in daily.columns}
    names = [c for c in daily.columns if c in by_name]
    ends = list(range(warmup, len(idx) - horizon + 1, step))
    if max_windows is not None:
        ends = ends[-max_windows:]
    rows: list[dict[str, Any]] = []
    hits = 0
    pending = 0
    for k in ends:
        asof = idx[k - 1]
        hist = daily.iloc[:k]
        fwd = daily.iloc[k:k + horizon][names]
        key = _digest(asof, list(arms), names, hist[names].to_numpy(dtype=float), seed, horizon,
                      data_key)
        books = cache.get(key)
        if isinstance(books, dict) and all(a in books for a in arms):
            hits += 1
        elif deadline is not None and time.time() > deadline:
            pending += 1
            continue
        else:
            books = {}
            for arm in arms:
                add = ArmInputs() if arm == "plain" else arm_inputs(arm, asof, hist)
                ev_t = [dataclasses.replace(
                    by_name[n], daily_r=hist[n].to_numpy(dtype=float),
                    macro_w=(np.asarray(add.macro_w[n], dtype=float)
                             if add.macro_w is not None and n in add.macro_w
                             else np.array([], dtype=float)))
                    for n in names]
                cfg = WorldConfig(seed=seed, n_worlds=N_WORLDS, n_rows=N_ROWS,
                                  regime_labels=add.regime_labels,
                                  regime_probs=add.regime_probs)
                books[arm] = {str(n): float(v) for n, v in solve(ev_t, cfg).items()}
            cache[key] = books
        rows.append({"asof": asof, "held_to": idx[min(k + horizon, len(idx)) - 1],
                     "growth": {a: realized_growth(books[a], fwd) for a in arms},
                     "total_heat": {a: round(sum(books[a].values()), 6) for a in arms}})
    verdicts = {a: paired_verdict([r["growth"][a] - r["growth"]["plain"] for r in rows])
                for a in arms if a != "plain"}
    return {"windows": rows, "verdicts": verdicts, "cache_hits": hits, "pending_windows": pending,
            "n_windows": len(rows), "horizon_days": horizon, "step_days": step}


# ------------------------------------------------------------------ the desk's own arms

def _desk_arm_inputs(arm: str, asof: str, hist: pd.DataFrame) -> ArmInputs:
    if arm == "regime":
        from research import pf_allocator as pa
        labels, probs, _ = pa.regime_state(hist, asof=asof)
        return ArmInputs(regime_labels=labels, regime_probs=probs)
    if arm == "macro":
        from libs.portfolio import macro_state
        dates = [str(d)[:10] for d in hist.index]
        w, meta = macro_state.kernel_weights(dates, asof=asof)
        if meta.get("status") != "MEASURED":
            return ArmInputs()
        return ArmInputs(macro_w={str(c): w for c in hist.columns})
    raise ValueError(f"unknown arm {arm!r}")


def _desk_solver() -> Callable[[list[SleeveEvidence], WorldConfig], Mapping[str, float]]:
    from research import pf_allocator as pa
    from research.heat_policy import HEAT_TARGET, per_sleeve_bounds

    def solve(ev_t: list[SleeveEvidence], cfg: WorldConfig) -> Mapping[str, float]:
        daily_t = pd.DataFrame({e.name: e.daily_r for e in ev_t})
        bounds = per_sleeve_bounds(pa.worst_dd_r(daily_t), HEAT_TARGET)
        return optimise(ev_t, hard_cap=HEAT_TARGET, target=None, cfg=cfg,
                        max_per_sleeve=bounds).heat
    return solve


def _data_key() -> str:
    """Size and mtime of every file the arms read besides the matrix, plus the solver's source."""
    import inspect

    from libs.portfolio import macro_state, robust_elog
    parts: list[Any] = [hashlib.sha256(inspect.getsource(robust_elog).encode()).hexdigest()]
    files = [BASE / "data" / "universe" / "XAUUSD_H1.parquet", macro_state.resolve_archive()]
    alfred = macro_state.ALFRED_DIR
    if alfred.is_dir():
        files += sorted(alfred.glob("*.parquet"))
    for f in files:
        try:
            st = f.stat()
            parts.append((str(f.name), st.st_size, st.st_mtime))
        except OSError:
            parts.append((str(f.name), None))
    return _digest(*parts)


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return dict(doc.get("windows") or {}) if doc.get("version") == VERSION else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=1, default=str, allow_nan=True), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def run(max_windows: int | None = MAX_WINDOWS, budget_s: float | None = BUDGET_S
        ) -> dict[str, Any]:
    """One measurement over the desk's evidence; writes `OUT`. Never touches the book."""
    from research import pf_allocator as pa
    t0 = time.time()
    daily, _forward = pa.build_evidence(force=False)
    daily = daily.sort_index()
    ev = pa.sleeve_evidence(daily, {}, pa.live_days_by_sleeve(), pa.search_trials())
    cache = _read_cache(CACHE)
    res = ablate(daily, ev, _desk_arm_inputs, solve=_desk_solver(),
                 max_windows=max_windows, cache=cache, data_key=_data_key(),
                 deadline=(t0 + budget_s) if budget_s else None)
    _write_json(CACHE, {"version": VERSION, "windows": cache})
    try:
        from libs.portfolio import macro_state
        vintage = macro_state.daily_states().get("vintage")
    except Exception as exc:                                  # pragma: no cover
        vintage = f"UNMEASURED ({type(exc).__name__})"
    doc = {"generated_utc": datetime.now(UTC).isoformat(), "version": VERSION,
           "status": "MEASURED" if res["n_windows"] else "UNMEASURED",
           "authority": "none: a measurement; the allocator reads it only via verdict_for",
           "rule": (f"arm minus plain realized log growth over non-overlapping {HORIZON}-day "
                    f"windows; PROMOTE/DEMOTE at |t| >= {T_DECIDE} with >= {MIN_PERIODS} "
                    f"windows, else UNPROVEN"),
           "macro_vintage": vintage, "n_sleeves": int(daily.shape[1]),
           "elapsed_s": round(time.time() - t0, 1), **res}
    _write_json(OUT, doc)
    return doc


def verdict_for(arm: str, path: Path = OUT) -> str:
    """PROMOTE, DEMOTE or UNPROVEN for one input; UNPROVEN on any read problem (fail closed)."""
    try:
        v = json.loads(path.read_text("utf-8"))["verdicts"][arm]["verdict"]
        return v if v in ("PROMOTE", "DEMOTE") else "UNPROVEN"
    except (OSError, ValueError, KeyError, TypeError):
        return "UNPROVEN"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-windows", type=int, default=MAX_WINDOWS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    doc = run(a.max_windows, a.budget_s)
    for arm, v in doc["verdicts"].items():
        print(f"{arm}: {v['verdict']} n={v['n_periods']} t={v.get('t')} ({v.get('why')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
