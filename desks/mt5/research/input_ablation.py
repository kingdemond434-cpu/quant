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

THE TEST. Walk forward over the desk's own daily matrix. At each rebalance day t, the sleeve
evidence is REBUILT from the history up to t (`_evidence_asof`: factor loadings fitted on those
days, no forward or live counts, one flat cost for every sleeve) and every arm re-solves on it --
the plain arm with no regime mix and no macro tilt, each input arm with exactly one of them read
AS OF t (`regime_state(asof=)`, `macro_state.kernel_weights(asof=)`) -- and the book it chose
is held over the next `HORIZON` days of REALIZED sleeve returns. The score is realized log
growth, log(1 + sum_i h_i r_i) summed over the holding window, and the verdict is a paired test
of arm minus plain over non-overlapping windows. Same worlds seed, same caps, same bounds on
every arm: the input is the only difference.

WHAT THE VERDICT MEANS. PROMOTE: the input added realized growth at |t| >= `t_bar` over at
least `MIN_PERIODS` measured windows, where `t_bar` is the larger of `T_DECIDE` and the
Bonferroni critical value for the number of inputs tested. DEMOTE: it cost growth at the same
bar, or it was ruined in a window the plain solve survived. UNPROVEN otherwise. A window where
an input could not be read (`ArmInputs.measured` False) is not a zero: it leaves that input's
sample. The bar is a constant here and never moves to let an input pass. The report has no
authority of its own: the allocator reads it only through `verdict_for` once that wiring is
audited.

LIMITS, SAID ONCE. A macro series with no ALFRED vintage is the current vintage, so its later
revisions leak into the replay: the macro arm may then never read PROMOTE (`PIT_REQUIRED`), only
UNPROVEN or DEMOTE. Each sleeve's trial count (deflation) is today's, the same on every arm. The
matrix is the desk's own evidence (backtest, forward and live rows aligned), not live fills.
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
#: Minimum measured non-overlapping windows before any verdict. DERIVATION (power): a paired test
#: at |t| >= 2 has power 0.8 against a standardised effect d when n*d^2 >= (2 + 0.84)^2 = 8.07;
#: n = 26 detects d = 0.56, half a year of weekly windows.
MIN_PERIODS = 26
#: Floor of the verdict bar on the paired t-statistic, aligned with `libs.regime.state_admission`
#: ADMIT_T (2.0), the only other out-of-sample gate on this desk. The bar actually used is the
#: larger of this and the Bonferroni critical value (`t_bar`).
T_DECIDE = 2.0
#: Family-wise two-sided significance across the inputs tested together, split Bonferroni-style:
#: 0.05 over 2 inputs at n = 26 is |t| >= 2.38 (Student t, 25 df).
FAMILY_ALPHA = 0.05
#: One flat cost per sleeve per trade in every replay: `pf_allocator.sleeve_evidence`'s own value
#: for a sleeve with no measured cost (0.05 R). Today's measured costs would leak into the past.
COST_R_FLAT = 0.05
#: Inputs whose PROMOTE needs every series it reads to be point-in-time (an ALFRED vintage).
PIT_REQUIRED = frozenset({"macro"})
#: World population for each replay solve: the allocator's own fast-clock population
#: (`pf_allocator.run`, mode fast: 128 worlds x 256 rows), per the cheapest solve the desk trusts.
N_WORLDS = 128
N_ROWS = 256
#: The plain solve and one arm per input under test; every arm solves under the same
#: `heat_policy.HEAT_TARGET` cap and per-sleeve bounds, so only the input differs.
ARMS = ("plain", "regime", "macro")
#: Windows the run keeps: the newest 52, a year of weekly windows, twice `MIN_PERIODS` so a
#: verdict can stand on one half and be re-checked on the other.
MAX_WINDOWS = 52
#: Wall-clock seconds one hourly pass may spend solving NEW windows; the rest wait for the next
#: hour's schedule (each solved window is cached as it finishes, so the backlog only shrinks).
#: DERIVATION: 600 s sits inside the hourly cycle's 720 s default leg cap
#: (`hourly_cycle.SEARCH_BUDGET_SEC`), leaving 120 s to score and write before the kill.
BUDGET_S = 600.0
#: Bump when the arm definitions or the score change; cached windows from another version are
#: re-solved, never reused.
VERSION = 2


@dataclasses.dataclass(frozen=True)
class ArmInputs:
    """What one arm adds to the plain solve at one rebalance day. `measured` False means the
    input could not be read as of that day: the window leaves that arm's sample."""
    regime_labels: tuple[str, ...] = ()
    regime_probs: tuple[tuple[str, float], ...] = ()
    macro_w: Mapping[str, np.ndarray] | None = None       # sleeve name -> weights over its rows
    measured: bool = True
    point_in_time: bool = True
    why: str = ""


def realized_growth(heat: Mapping[str, float], fwd: pd.DataFrame) -> float:
    """sum_d log(1 + sum_i h_i r_{i,d}) over the holding window; -inf on ruin."""
    if fwd.empty:
        return 0.0
    h = np.array([float(heat.get(str(c), 0.0)) for c in fwd.columns])
    port = np.nan_to_num(fwd.to_numpy(dtype=float), nan=0.0) @ h
    if np.any(port <= -1.0):
        return float("-inf")
    return float(np.log1p(port).sum())


def t_bar(n: int, n_inputs: int) -> float:
    """max(T_DECIDE, Bonferroni two-sided critical t at FAMILY_ALPHA over `n_inputs`)."""
    k = max(int(n_inputs), 1)
    q = 1.0 - FAMILY_ALPHA / (2.0 * k)
    try:
        from scipy.stats import t as student_t
        crit = float(student_t.ppf(q, max(n - 1, 1)))
    except Exception:                                          # pragma: no cover
        from statistics import NormalDist
        crit = NormalDist().inv_cdf(q) * (1.0 + 1.0 / max(n - 1, 1))
    return max(T_DECIDE, crit)


def paired_verdict(pairs: Sequence[tuple[float | None, float | None]], *,
                   n_inputs: int = 1) -> dict[str, Any]:
    """(arm, plain) realized growth per non-overlapping window. A None on either side is an
    unmeasured window and leaves the sample; ruin is decided before any statistic."""
    ruined = survived = unmeasured = 0
    diffs: list[float] = []
    for a, p in pairs:
        if a is None or p is None or (a == -math.inf and p == -math.inf):
            unmeasured += 1
        elif a == -math.inf:
            ruined += 1
        elif p == -math.inf:
            survived += 1
        else:
            diffs.append(float(a) - float(p))
    d = np.array(diffs, dtype=float)
    n = int(d.size)
    bar = t_bar(n, n_inputs)
    out: dict[str, Any] = {"n_periods": n, "min_periods": MIN_PERIODS, "t_bar": round(bar, 3),
                           "unmeasured_windows": unmeasured, "ruined_windows": ruined,
                           "plain_ruined_windows": survived, "t": None}
    if ruined:
        out.update(verdict="DEMOTE", why=f"ruined in {ruined} window(s) the plain solve survived")
        return out
    if n < 2:
        out.update(verdict="UNPROVEN", why=f"{n} measured window(s); {MIN_PERIODS} needed")
        return out
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    out.update(mean_log_growth_diff=round(mean, 8), sd=round(sd, 8),
               total_log_growth_diff=round(float(d.sum()), 8))
    if not sd > 1e-12 * max(1.0, abs(mean)):          # floating-point zero, not a variance
        out.update(verdict="UNPROVEN", why="no variation between arm and plain: nothing to test")
        return out
    t = mean / (sd / math.sqrt(n))
    out["t"] = round(t, 3)
    if n < MIN_PERIODS:
        out.update(verdict="UNPROVEN", why=f"{n} measured window(s); {MIN_PERIODS} needed")
    elif t >= bar:
        out.update(verdict="PROMOTE", why=f"beats the plain solve out of sample at t={t:.2f}")
    elif t <= -bar:
        out.update(verdict="DEMOTE", why=f"loses to the plain solve out of sample at t={t:.2f}")
    else:
        out.update(verdict="UNPROVEN", why=f"|t|={abs(t):.2f} < {bar:.2f}")
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


def ablate(daily: pd.DataFrame,
           evidence_asof: Callable[[pd.DataFrame], Sequence[SleeveEvidence]],
           arm_inputs: Callable[[str, str, pd.DataFrame], ArmInputs], *,
           solve: Callable[[list[SleeveEvidence], WorldConfig], Mapping[str, float]],
           arms: Sequence[str] = ARMS, horizon: int = HORIZON, step: int = STEP,
           warmup: int = WARMUP, max_windows: int | None = None,
           cache: dict[str, Any] | None = None, seed: int = 0,
           window_key: Callable[[str], str] | None = None, deadline: float | None = None,
           on_window: Callable[[], None] | None = None) -> dict[str, Any]:
    """Walk-forward ablation.

    `evidence_asof(history)` builds the sleeve evidence from `history` (rows up to and including
    the rebalance day) only; `arm_inputs(arm, asof_day, history)` returns what that arm adds,
    from the same rows; `solve` is the allocator. `cache` maps a window's digest to its books, so
    a later pass re-solves only new windows; `window_key(asof_day)` digests everything the arms
    read besides the matrix AS OF that day, so a revised input re-solves its windows and an
    appended bar does not. Past `deadline` (epoch seconds) no new window is solved. `on_window`
    is called after each newly solved window (the caller persists the cache there).
    """
    cache = {} if cache is None else cache
    idx = [str(d)[:10] for d in daily.index]
    ends = list(range(warmup, len(idx) - horizon + 1, step))
    if max_windows is not None:
        ends = ends[-max_windows:]
    rows: list[dict[str, Any]] = []
    hits = 0
    pending = 0
    for k in ends:
        asof = idx[k - 1]
        hist = daily.iloc[:k]
        key = _digest(asof, list(arms), [str(c) for c in hist.columns],
                      hist.to_numpy(dtype=float), seed, horizon,
                      window_key(asof) if window_key else "")
        books = cache.get(key)
        if isinstance(books, dict) and all(a in books for a in arms):
            hits += 1
        elif deadline is not None and time.time() > deadline:
            pending += 1
            continue
        else:
            ev = {e.name: e for e in evidence_asof(hist)}
            names = [str(c) for c in hist.columns if c in ev]
            books = {}
            for arm in arms:
                add = ArmInputs() if arm == "plain" else arm_inputs(arm, asof, hist)
                if not add.measured:
                    books[arm] = {"unmeasured": add.why or "input not readable as of this day"}
                    continue
                ev_t = [dataclasses.replace(
                    ev[n],
                    macro_w=(np.asarray(add.macro_w[n], dtype=float)
                             if add.macro_w is not None and n in add.macro_w
                             else np.array([], dtype=float)))
                    for n in names]
                cfg = WorldConfig(seed=seed, n_worlds=N_WORLDS, n_rows=N_ROWS,
                                  regime_labels=add.regime_labels,
                                  regime_probs=add.regime_probs)
                books[arm] = {"heat": {str(n): float(v) for n, v in solve(ev_t, cfg).items()},
                              "point_in_time": bool(add.point_in_time)}
            cache[key] = books
            if on_window is not None:
                on_window()
        fwd = daily.iloc[k:k + horizon]
        growth: dict[str, float | None] = {
            a: (realized_growth(books[a]["heat"], fwd) if "heat" in books[a] else None)
            for a in arms}
        rows.append({"asof": asof, "held_to": idx[min(k + horizon, len(idx)) - 1],
                     "growth": growth,
                     "point_in_time": {a: bool(books[a].get("point_in_time", True))
                                       for a in arms if "heat" in books[a]},
                     "unmeasured": {a: books[a]["unmeasured"] for a in arms
                                    if "unmeasured" in books[a]}})
    inputs = [a for a in arms if a != "plain"]
    verdicts: dict[str, Any] = {}
    for a in inputs:
        v = paired_verdict([(r["growth"][a], r["growth"]["plain"]) for r in rows],
                           n_inputs=len(inputs))
        if a in PIT_REQUIRED and v["verdict"] == "PROMOTE" and not all(
                r["point_in_time"].get(a, False) for r in rows if r["growth"][a] is not None):
            v.update(verdict="UNPROVEN",
                     why=("would PROMOTE, but a series it reads is not point-in-time (no ALFRED "
                          "vintage), so later revisions may be what it won on"))
        verdicts[a] = v
    return {"windows": rows, "verdicts": verdicts, "cache_hits": hits, "pending_windows": pending,
            "n_windows": len(rows), "horizon_days": horizon, "step_days": step}


# ------------------------------------------------------------------ the desk's own arms

def _evidence_asof(trials: Mapping[str, int]) -> Callable[[pd.DataFrame], list[SleeveEvidence]]:
    from research import pf_allocator as pa

    def build(hist: pd.DataFrame) -> list[SleeveEvidence]:
        ev = pa.sleeve_evidence(hist, {}, {}, dict(trials))
        return [dataclasses.replace(e, cost_r=COST_R_FLAT, cost_bias_r=0.0, forward_days=0,
                                    live_days=0) for e in ev]
    return build


def _desk_arm_inputs(arm: str, asof: str, hist: pd.DataFrame) -> ArmInputs:
    if arm == "regime":
        from research import pf_allocator as pa
        labels, probs, _ = pa.regime_state(hist, asof=asof)
        if not probs:
            return ArmInputs(measured=False, why="regime engine could not fit as of this day")
        return ArmInputs(regime_labels=labels, regime_probs=probs)
    if arm == "macro":
        from libs.portfolio import macro_state
        dates = [str(d)[:10] for d in hist.index]
        w, meta = macro_state.kernel_weights(dates, asof=asof)
        if meta.get("status") != "MEASURED":
            return ArmInputs(measured=False,
                             why=f"macro kernel {meta.get('status')}: {meta.get('why', '')}")
        by_series = macro_state.daily_states().get("vintage_by_series") or {}
        pit = bool(meta.get("dims")) and all(
            by_series.get(macro_state.SERIES.get(d, "")) == macro_state.VINTAGE_ALFRED
            for d in meta["dims"])
        return ArmInputs(macro_w={str(c): w for c in hist.columns}, point_in_time=pit)
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


def _desk_window_key(trials: Mapping[str, int]) -> Callable[[str], str]:
    """What the arms and the evidence read besides the matrix, AS OF a day: the solver's source,
    the trial counts, the gold daily closes up to the day (the regime arm's input) and the macro
    kernel states up to the day with their vintages (the macro arm's). An hourly bar appended
    after the day changes nothing; a revised print on or before it re-solves the window."""
    import inspect

    from libs.portfolio import macro_state, robust_elog
    base = [hashlib.sha256(inspect.getsource(robust_elog).encode()).hexdigest(),
            sorted(trials.items())]
    closes: pd.Series | None = None
    try:
        px = pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet")
        col = next((c for c in ("close", "Close", "c") if c in px.columns), None)
        tcol = next((c for c in ("time", "Time", "datetime") if c in px.columns), None)
        if col is not None:
            ix = pd.to_datetime(px[tcol] if tcol else px.index, utc=True, errors="coerce")
            c = pd.Series(px[col].to_numpy(dtype=float), index=ix).dropna()
            closes = c.groupby(c.index.date).last()
            closes.index = [str(d) for d in closes.index]
    except Exception:
        closes = None
    try:
        doc = macro_state.daily_states()
        states, vint = doc.get("states") or {}, doc.get("vintage_by_series") or {}
    except Exception:
        states, vint = {}, {}

    def key(asof: str) -> str:
        cut = str(asof)[:10]
        gold = (closes[[d <= cut for d in closes.index]].to_numpy(dtype=float)
                if closes is not None else "no-gold")
        macro = {d: sorted((k, v) for k, v in by.items() if k <= cut)
                 for d, by in states.items() if d in macro_state.KERNEL_DIMS}
        return _digest(base, gold, macro, sorted(vint.items()))
    return key


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
    trials = pa.search_trials()
    cache = _read_cache(CACHE)

    def persist() -> None:
        _write_json(CACHE, {"version": VERSION, "windows": cache})

    res = ablate(daily, _evidence_asof(trials), _desk_arm_inputs, solve=_desk_solver(),
                 max_windows=max_windows, cache=cache, window_key=_desk_window_key(trials),
                 deadline=(t0 + budget_s) if budget_s else None, on_window=persist)
    persist()
    status = ("UNMEASURED" if not res["n_windows"]
              else "PARTIAL" if res["pending_windows"] else "MEASURED")
    doc = {"generated_utc": datetime.now(UTC).isoformat(), "version": VERSION, "status": status,
           "authority": "none: a measurement; the allocator reads it only via verdict_for",
           "rule": (f"arm minus plain realized log growth over non-overlapping {HORIZON}-day "
                    f"windows on evidence rebuilt as of each window; PROMOTE/DEMOTE at |t| >= "
                    f"max({T_DECIDE}, Bonferroni t at {FAMILY_ALPHA} over the inputs) with >= "
                    f"{MIN_PERIODS} measured windows, DEMOTE on a ruin the plain solve survived, "
                    f"else UNPROVEN; {sorted(PIT_REQUIRED)} may PROMOTE only on point-in-time "
                    f"series"),
           "limits": ["trial counts (deflation) are today's, identical on every arm",
                      f"one flat cost of {COST_R_FLAT} R per sleeve in every replay"],
           "n_sleeves": int(daily.shape[1]), "elapsed_s": round(time.time() - t0, 1), **res}
    _write_json(OUT, doc)
    return doc


def verdict_for(arm: str, path: Path = OUT) -> str:
    """PROMOTE, DEMOTE or UNPROVEN for one input; UNPROVEN on any read problem, and on any
    report that is not a complete measurement (fail closed)."""
    try:
        doc = json.loads(path.read_text("utf-8"))
        if doc.get("status") != "MEASURED":
            return "UNPROVEN"
        v = doc["verdicts"][arm]["verdict"]
        return v if v in ("PROMOTE", "DEMOTE") else "UNPROVEN"
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return "UNPROVEN"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-windows", type=int, default=MAX_WINDOWS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    doc = run(a.max_windows, a.budget_s)
    print(f"input ablation {doc['status']}: {doc['n_windows']} window(s), "
          f"{doc['pending_windows']} pending")
    for arm, v in doc["verdicts"].items():
        print(f"{arm}: {v['verdict']} n={v['n_periods']} t={v.get('t')} ({v.get('why')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
