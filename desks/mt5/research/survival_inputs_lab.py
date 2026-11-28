"""THE SURVIVAL INPUTS LAB -- per-symbol and per-sleeve tail index (Hill + POT), the tail's cost
in growth-optimal size, and the microstructure-noise ratio / signature plot per symbol.

    GAP_MAP rows (Max-growth; Max-growth (cost) + State-engine), built 2026-11-13:
      "Per-symbol extreme-value tail index (Hill/POT) as a survival-sizing input"
      "Microstructure-noise ratio / signature plot per symbol"

WHAT IT READS (box state; an absent input is UNMEASURED and named):
    data/universe/<SYM>_H1.parquet           every symbol's bars -> daily and hourly log returns
    data/universe/<SYM>_M1.parquet           the bars-only noise fallback where there is no tape
    data/tape/ticks/<SYM>/<YYYY-MM-DD>.parquet  the venue's own quotes (ts, bid, ask)
    data/pf_allocator_cache/daily_r.parquet  the allocator's per-sleeve daily R

WHAT IT WRITES:
    reports/SURVIVAL_INPUTS.json             the full measurement
    data/survival_inputs.json                the compact consumer map:
        symbols.<SYM> = {tail_alpha_loss, xi, es995_ratio, kelly_ratio, nsr, min_horizon_s,
                         d_opt_s, roll_over_quoted}
        sleeves.<name> = {tail_alpha_loss, xi, es995_ratio, kelly_ratio}
        proof = {tail_tilt, tail_scaled: verdict}
    data/survival_inputs_history.jsonl       one summary row per run

THE PROOF (Rule 1). A tail-aware size is only an input if it raises realised log growth. At each
monthly rebalance the lab estimates every sleeve's growth-optimal fraction on its trailing 500
days twice -- Gaussian (mu/s^2) and on the spliced empirical+GPD distribution -- and holds two
books out of sample against the Gaussian one at the 20% floor:
    tail_tilt    the spliced fractions, rescaled to the same total heat (direction only)
    tail_scaled  the spliced fractions at their own total, inside [20%, 30%] (two-sided)
Paired Newey-West test on daily log growth: ADOPT only on a positive 90% lower bound.

The noise reading's proof is calibration rather than growth: the Roll effective spread against
the quoted spread the cost model charges (`roll_over_quoted` > 1 means the venue's realised
noise costs more than its quote), published per symbol for the cost surface.

AUTHORITY: none in this change -- measurement and verdicts only.

    python desks/mt5/research/survival_inputs_lab.py --once [--budget-s 900]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.risk import microstructure_noise as mn  # noqa: E402
from libs.risk import tail_index as ti  # noqa: E402

R = DESK / "reports"
DATA = DESK / "data"
OUT = R / "SURVIVAL_INPUTS.json"
COMPACT = DATA / "survival_inputs.json"
HISTORY = DATA / "survival_inputs_history.jsonl"
UNIVERSE = DATA / "universe"
TAPE = DATA / "tape" / "ticks"
PANEL = DATA / "pf_allocator_cache" / "daily_r.parquet"

TAPE_DAYS = 10
HEAT_FLOOR, HEAT_CEILING = 0.20, 0.30
TRAIN, HOLD = 500, 21
PROOF_SIM_N = 20_000
NW_LAG, PROOF_Z, MIN_OOS_DAYS = 5, 1.645, 120
#: A book day below this is clipped before the log; every clip is counted and published.
CLIP_R = -0.95


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _clean(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return float(f"{f:.8g}") if math.isfinite(f) else None
    if isinstance(v, np.integer):
        return int(v)
    return v


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(_clean(doc), fh, indent=1)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------- inputs
def symbols_in(universe: Path = UNIVERSE) -> list[str]:
    return sorted(p.name[: -len("_H1.parquet")] for p in universe.glob("*_H1.parquet"))


def returns_of(symbol: str, universe: Path = UNIVERSE) -> tuple[np.ndarray, np.ndarray]:
    """(daily, hourly) log returns from H1 closes; daily = last close per UTC date."""
    p = universe / f"{symbol}_H1.parquet"
    try:
        df = pd.read_parquet(p, columns=["close"])
    except Exception:
        return np.array([]), np.array([])
    idx = pd.to_datetime(df.index, utc=True, errors="coerce")
    s = pd.Series(df["close"].to_numpy(float), index=idx).dropna()
    s = s[s > 0].sort_index()
    if s.size < 3:
        return np.array([]), np.array([])
    hourly = np.diff(np.log(s.to_numpy()))
    d = s.groupby(s.index.normalize()).last()
    daily = np.diff(np.log(d.to_numpy()))
    return daily, hourly


def tape_days(symbol: str, tape: Path = TAPE, days: int = TAPE_DAYS) -> list[pd.DataFrame]:
    d = tape / symbol
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.parquet"))[-days:]:
        try:
            df = pd.read_parquet(p)
        except Exception:
            continue
        if {"ts", "bid", "ask"} <= set(df.columns):
            out.append(df[["ts", "bid", "ask"]])
    return out


def m1_closes(symbol: str, universe: Path = UNIVERSE) -> np.ndarray | None:
    p = universe / f"{symbol}_M1.parquet"
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p, columns=["close"])["close"].to_numpy(float)[-50_000:]
    except Exception:
        return None


# ---------------------------------------------------------------------------- proof
def _inlife_zero(x: np.ndarray) -> np.ndarray:
    """NaN -> 0 between each column's first and last observation; NaN outside its life."""
    x = np.asarray(x, dtype=float).copy()
    ok = np.isfinite(x)
    if not ok.any():
        return x
    first = np.where(ok.any(axis=0), ok.argmax(axis=0), x.shape[0])
    last = np.where(ok.any(axis=0), x.shape[0] - 1 - ok[::-1].argmax(axis=0), -1)
    rows = np.arange(x.shape[0])[:, None]
    x[(rows >= first[None, :]) & (rows <= last[None, :]) & ~ok] = 0.0
    return x


def paired_verdict(d: np.ndarray, z: float = PROOF_Z) -> dict[str, Any]:
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    if d.size < MIN_OOS_DAYS:
        return {"verdict": "UNMEASURED", "oos_days": int(d.size)}
    mu = float(d.mean())
    u = d - mu
    s = float(u @ u) / d.size
    for k in range(1, NW_LAG + 1):
        s += 2.0 * (1.0 - k / (NW_LAG + 1.0)) * float(u[k:] @ u[:-k]) / d.size
    se = math.sqrt(max(s, 0.0) / d.size)
    lo, hi = mu - z * se, mu + z * se
    return {"verdict": "ADOPT" if lo > 0 else ("REJECT" if hi < 0 else "INCONCLUSIVE"),
            "oos_days": int(d.size), "delta_elog_annual": mu * 252,
            "t": mu / se if se > 0 else None, "ci90_daily": [lo, hi]}


def _scale(w: np.ndarray, total: float) -> np.ndarray:
    s = float(np.clip(w, 0, None).sum())
    out: np.ndarray = np.clip(w, 0, None) * (total / s) if s > 0 else np.zeros_like(w)
    return out


def proof(panel: pd.DataFrame, *, budget_s: float, clock=time.monotonic) -> dict[str, Any]:
    t0 = clock()
    x = panel.to_numpy(float)
    logs: dict[str, list[float]] = {"gauss": [], "tail_tilt": [], "tail_scaled": []}
    clips: dict[str, int] = dict.fromkeys(logs, 0)
    rebal = 0
    rng = np.random.default_rng(0)
    for start in range(TRAIN, x.shape[0] - 1, HOLD):
        if clock() - t0 > budget_s:
            break
        # In-life zero fill on BOTH sides: the hold scores a non-trading day as 0, so the
        # estimate it is scored against must count it the same way.
        tr = _inlife_zero(x[start - TRAIN:start])
        te = np.nan_to_num(x[start:start + HOLD], nan=0.0)
        n = tr.shape[1]
        fg = np.zeros(n)
        fs = np.zeros(n)
        for j in range(n):
            col = tr[:, j]
            col = col[np.isfinite(col)]
            if col.size < ti.MIN_OBS:
                continue
            g, s, _r = ti.kelly_ratio(col, rng, PROOF_SIM_N)
            if g is not None and s is not None:
                fg[j], fs[j] = g, s
        if fg.sum() <= 0:
            continue
        rebal += 1
        base = _scale(fg, HEAT_FLOOR)
        tilt = _scale(fs, HEAT_FLOOR)
        own = float(HEAT_FLOOR * fs.sum() / fg.sum())
        scaled = _scale(fs, min(HEAT_CEILING, max(HEAT_FLOOR, own)))
        for name, w in (("gauss", base), ("tail_tilt", tilt), ("tail_scaled", scaled)):
            r = te @ w
            clips[name] += int((r < CLIP_R).sum())
            logs[name].extend(np.log1p(np.clip(r, CLIP_R, None)).tolist())
    g = np.array(logs["gauss"])
    out: dict[str, Any] = {"rebalances": rebal, "train_days": TRAIN, "hold_days": HOLD,
                           "baseline": "gauss (mu/s^2 per sleeve, 20% total heat)",
                           "elog_annual_gauss": float(g.mean() * 252) if g.size else None}
    from statistics import NormalDist
    family = 2
    z_fw = NormalDist().inv_cdf(1.0 - 0.05 / family)
    for k in ("tail_tilt", "tail_scaled"):
        a = np.array(logs[k])
        if a.size == g.size and a.size:
            out[k] = paired_verdict(a - g)
            fw = paired_verdict(a - g, z_fw)
            out[k].update({"family_size": family, "verdict_familywise": fw["verdict"],
                           "loss_clip_days": clips[k], "baseline_clip_days": clips["gauss"]})
        else:
            out[k] = {"verdict": "UNMEASURED", "oos_days": 0}
    return out


# ---------------------------------------------------------------------------- measurement
def _tail_row(tr: ti.TailReading | None) -> dict[str, Any] | None:
    if tr is None:
        return None
    return {"n": tr.n, "tail_alpha_loss": tr.loss_hill.get("alpha"),
            "tail_alpha_loss_ci90": tr.loss_hill.get("ci90"),
            "tail_alpha_gain": tr.gain_hill.get("alpha"),
            "xi": tr.loss_pot.get("xi"), "es995_gpd": tr.loss_pot.get("es995"),
            "es995_gauss": tr.gaussian.get("es995"), "es995_ratio": tr.es995_ratio,
            "var995_gpd": tr.loss_pot.get("var995"),
            "kelly_gauss": tr.kelly_gauss, "kelly_spliced": tr.kelly_spliced,
            "kelly_ratio": tr.kelly_ratio}


def measure(*, universe: Path = UNIVERSE, tape: Path = TAPE, panel_path: Path = PANEL,
            budget_s: float = 900.0, clock=time.monotonic) -> dict[str, Any]:
    t0 = clock()
    rng = np.random.default_rng(7)
    syms = symbols_in(universe)
    doc: dict[str, Any] = {"at": _now(), "symbols_seen": len(syms)}
    symbols: dict[str, Any] = {}
    deferred: list[str] = []
    for sym in syms:
        if clock() - t0 > 0.45 * budget_s:
            deferred.append(sym)
            continue
        daily, hourly = returns_of(sym, universe)
        row: dict[str, Any] = {"daily": _tail_row(ti.measure(daily, rng=rng, sim_n=50_000,
                                                             boot=100)),
                               "hourly": _tail_row(ti.measure(hourly, rng=rng, sim_n=50_000,
                                                              boot=100))}
        days = tape_days(sym, tape)
        if days:
            row["noise"] = mn.pool(mn.day_reading(d) for d in days)
        else:
            m1 = m1_closes(sym, universe)
            row["noise"] = (mn.from_bars(m1) if m1 is not None else
                            {"status": "UNMEASURED", "why": "no tape and no M1 bars"})
        symbols[sym] = row
    doc["symbols"] = symbols
    doc["symbols_deferred_by_budget"] = deferred

    sleeves: dict[str, Any] = {}
    panel = None
    if panel_path.exists():
        try:
            panel = pd.read_parquet(panel_path).apply(pd.to_numeric, errors="coerce")
            panel.index = pd.to_datetime([str(i) for i in panel.index], utc=True,
                                         errors="coerce")
            panel = panel[~panel.index.isna()].sort_index()
        except Exception as exc:
            # type only: pyarrow messages carry the box's absolute paths into a committed file
            doc["panel_why"] = f"{panel_path.name} unreadable: {type(exc).__name__}"
            panel = None
    if panel is not None:
        for c in panel.columns:
            if clock() - t0 > 0.65 * budget_s:
                break
            col = _inlife_zero(panel[[c]].to_numpy(float))[:, 0]
            sleeves[str(c)] = _tail_row(ti.measure(col[np.isfinite(col)], rng=rng,
                                                   sim_n=50_000, boot=100))
        doc["proof"] = proof(panel, budget_s=max(30.0, budget_s - (clock() - t0) - 10.0),
                             clock=clock)
    else:
        doc.setdefault("panel_why", f"{panel_path.name} absent")
        doc["proof"] = {"tail_tilt": {"verdict": "UNMEASURED"},
                        "tail_scaled": {"verdict": "UNMEASURED"}}
    doc["sleeves"] = {k: v for k, v in sleeves.items() if v is not None}
    doc["sleeves_too_short"] = sum(1 for v in sleeves.values() if v is None)
    alphas = [r["daily"]["tail_alpha_loss"] for r in symbols.values()
              if r.get("daily") and r["daily"].get("tail_alpha_loss")]
    noisy = sorted(((s, r["noise"].get("nsr")) for s, r in symbols.items()
                    if (r.get("noise") or {}).get("nsr") is not None), key=lambda kv: -kv[1])
    doc["summary"] = {
        "symbols_with_daily_tail": len(alphas),
        "median_daily_loss_alpha": float(np.median(alphas)) if alphas else None,
        "fattest_tails": sorted(((s, r["daily"]["tail_alpha_loss"]) for s, r in symbols.items()
                                 if r.get("daily") and r["daily"].get("tail_alpha_loss")),
                                key=lambda kv: kv[1])[:10],
        "symbols_with_tick_noise": len(noisy),
        "noisiest": noisy[:10],
        "sleeves_measured": len(doc["sleeves"]),
        "proof": {k: (doc["proof"].get(k) or {}).get("verdict")
                  for k in ("tail_tilt", "tail_scaled")}}
    full = bool(symbols) and panel is not None and not deferred
    doc["status"] = "MEASURED" if full else ("PARTIAL" if symbols or sleeves else "UNMEASURED")
    doc["elapsed_s"] = round(clock() - t0, 1)
    return doc


def compact(doc: dict[str, Any]) -> dict[str, Any]:
    syms = {}
    for s, r in (doc.get("symbols") or {}).items():
        d = r.get("daily") or {}
        n = r.get("noise") or {}
        syms[s] = {"tail_alpha_loss": d.get("tail_alpha_loss"), "xi": d.get("xi"),
                   "es995_ratio": d.get("es995_ratio"), "kelly_ratio": d.get("kelly_ratio"),
                   "noise_status": n.get("status"), "nsr": n.get("nsr"),
                   "min_horizon_s": n.get("min_horizon_s"), "d_opt_s": n.get("d_opt_s"),
                   "roll_over_quoted": n.get("roll_over_quoted")}
    sl = {k: {"tail_alpha_loss": v.get("tail_alpha_loss"), "xi": v.get("xi"),
              "es995_ratio": v.get("es995_ratio"), "kelly_ratio": v.get("kelly_ratio")}
          for k, v in (doc.get("sleeves") or {}).items()}
    return {"at": doc.get("at"), "status": doc.get("status"), "symbols": syms, "sleeves": sl,
            "proof": (doc.get("summary") or {}).get("proof"),
            "authority": "none: measurement and verdicts; a consumer needs an ADOPT verdict "
                         "and an audited change"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=900.0)
    a = ap.parse_args(argv)
    doc = measure(budget_s=a.budget_s)
    _write(OUT, doc)
    _write(COMPACT, compact(doc))
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(_clean({"at": doc["at"], "status": doc["status"],
                                    **doc["summary"]})) + "\n")
    print(f"survival inputs: {doc['status']} -- {doc['summary']['symbols_with_daily_tail']} "
          f"symbol tails, {doc['summary']['symbols_with_tick_noise']} tick-noise readings, "
          f"{doc['summary']['sleeves_measured']} sleeves; proof {doc['summary']['proof']}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
