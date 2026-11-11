"""STRATEGY-HEALTH LAB: do the desk's decay detectors beat a simple baseline? (DECAY-06, DECAY-13)

Mandate 2026-10-06 (Growth allocator overhaul):
  DECAY-06 "Compare EWMA adaptation, Bayesian online change-point detection and regime-
           conditioned persistence against simple baselines; do not multiply penalties."
  DECAY-13 "Validate against stable/noisy, gradually decaying, abruptly broken, temporarily
           unsuitable, cost-impaired, recovering and shared-failure cases; measure detection
           delay, false retirements, reinstatement errors vs simpler baselines."

Neither existed. `decay_regime` was calibrated on three synthetic families inside its unit tests,
and nothing ever compared it against the plain t-rule it adjusts, on paths where the TRUTH is
known. This lab does that every day and publishes the table.

THE DETECTORS (each reads a sleeve's trailing trade-R window, up to `WINDOW` trades, and says
DEAD or ALIVE):
    t_rule     the simple baseline: trailing mean t-stat <= -`T_DEAD` at n >= `MIN_N`
    ewma       exponentially weighted mean and variance (half-life `EWMA_HALFLIFE` trades),
               DEAD when the EWMA mean is `T_DEAD` standard errors below zero
    bocpd      `decay_regime.bocpd`: DEAD on a recent change-point whose current run is negative
               (the same break rule `decay_regime.classify` uses)
    regime     `decay_regime.classify`: DEAD on STRUCTURAL_BREAK or PERSISTENT_BAD_REGIME

THE CASES (the truth is known for every trade):
    stable          mean +0.15R, sd 1, never breaks
    noisy           mean +0.05R, sd 2, never breaks
    gradual         +0.20R sliding linearly to -0.20R from trade 40; dead once the mean < 0
    abrupt          +0.20R, then -0.30R from trade 60
    temporary       +0.20R with a -0.30R stretch over trades 50-69, then healthy again
    cost_impaired   +0.20R gross, then a 0.30R cost appears from trade 60 (net -0.10R)
    recovering      -0.20R over trades 20-59 (dead), then +0.20R (alive again)
    shared_failure  `SHARED_K` sleeves on one common factor that all break at trade 60: the
                    question is whether the detector retires them as ONE event or K

THE SCORES per detector per case, over `PATHS` seeded paths:
    false_retire    share of paths flagged DEAD at a step where the truth was ALIVE
    delay           median trades from the true break to the first DEAD flag (None when never)
    missed          share of broken paths never flagged by the end
    reinstate_err   share of recovering/temporary paths still flagged DEAD `REINSTATE_K` trades
                    after the truth came back
    shared_events   for shared_failure: the number of distinct flag times across the K sleeves
                    (1 = one event; K = K independent-looking retirements)

THE VERDICT is per detector versus `t_rule`: BEATS_BASELINE when, over the broken cases, its
median delay is shorter and its missed share no higher, AND its false-retire share over the
healthy cases is no higher; LOSES when it is no better on all three; MIXED otherwise. (A delay
is measured only on caught paths, so delay alone would reward a detector that misses most
breaks.) That is published. It moves no capital:
the live ladder stays `decay_monitor` + one-step `decay_regime.adjust`, one penalty, never two.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "HEALTH_LAB.json"
#: Trades per synthetic path. 120 trades is about six months of a daily sleeve.
LENGTH = 120
#: Trailing window each detector reads. 60 trades bounds BOCPD's exact run-length posterior.
WINDOW = 60
#: Steps between evaluations. Every 5th trade keeps one full pass inside the leg budget.
STEP = 5
#: Seeded paths per case. DERIVATION: 16 paths give a false-retire share a standard error of
#: at most sqrt(0.25/16) = 0.125, enough to rank detectors, and fit one pass in about 60 s.
PATHS = 16
#: Minimum trades before any detector speaks. 12 is `decay_regime.MIN_N`.
MIN_N = 12
#: t threshold for the baseline and EWMA rules. 2.0 is the desk's standing decision bar
#: (`input_ablation.T_DECIDE` = 2.0).
T_DEAD = 2.0
#: EWMA half-life in trades. 20 trades is the decay ladder's own minimum sample (n >= 20).
EWMA_HALFLIFE = 20.0
#: Trades after the truth recovers before a still-DEAD flag counts as a reinstatement error.
#: 20 trades is the same minimum sample a fresh sleeve would need to be judged again.
REINSTATE_K = 20
#: Sleeves in the shared-failure case. 8 is the desk's typical funded-book size.
SHARED_K = 8
#: Run the lab at most once per this many seconds (derived: the cases are synthetic, so a
#: daily 24 * 3600 s refresh only catches detector code changes, which land at most daily).
EVERY_S = 24 * 3600
BUDGET_S = 300.0


# ------------------------------------------------------------------ detectors

def t_rule(rs: list[float]) -> bool:
    x = np.asarray(rs[-WINDOW:], dtype=float)
    if x.size < MIN_N:
        return False
    sd = float(x.std(ddof=1))
    if not sd > 0:
        return bool(x.mean() < 0)
    return float(x.mean()) / (sd / math.sqrt(x.size)) <= -T_DEAD


def ewma(rs: list[float]) -> bool:
    x = np.asarray(rs[-WINDOW:], dtype=float)
    if x.size < MIN_N:
        return False
    lam = 0.5 ** (1.0 / EWMA_HALFLIFE)
    w = lam ** np.arange(x.size)[::-1]
    w = w / w.sum()
    m = float((w * x).sum())
    v = float((w * (x - m) ** 2).sum())
    n_eff = 1.0 / float((w * w).sum())
    se = math.sqrt(v / n_eff) if v > 0 else 0.0
    return m < 0 and (se == 0.0 or m / se <= -T_DEAD)


def bocpd_rule(rs: list[float]) -> bool:
    from research import decay_regime as dr
    x = [float(r) for r in rs[-WINDOW:]]
    if len(x) < MIN_N:
        return False
    cp = dr.bocpd(x)
    return bool(cp["p_recent_break"] >= dr.BREAK_P_RECENT and cp["run_p_neg"] >= dr.BREAK_P_NEG
                and cp["map_run"] >= dr.BREAK_MIN_RUN)


def regime_rule(rs: list[float]) -> bool:
    from research import decay_regime as dr
    c = dr.classify([float(r) for r in rs[-WINDOW:]])
    return c.get("class") in ("STRUCTURAL_BREAK", "PERSISTENT_BAD_REGIME")


DETECTORS: dict[str, Callable[[list[float]], bool]] = {
    "t_rule": t_rule, "ewma": ewma, "bocpd": bocpd_rule, "regime": regime_rule}
BASELINE = "t_rule"


# ------------------------------------------------------------------ cases

def _case(name: str, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """(trade R, alive?) for one path of `LENGTH` trades."""
    t = np.arange(LENGTH)
    if name == "stable":
        mu, sd = np.full(LENGTH, 0.15), 1.0
    elif name == "noisy":
        mu, sd = np.full(LENGTH, 0.05), 2.0
    elif name == "gradual":
        mu = np.where(t < 40, 0.20, 0.20 - 0.40 * (t - 40) / (LENGTH - 40))
        sd = 1.0
    elif name == "abrupt":
        mu, sd = np.where(t < 60, 0.20, -0.30), 1.0
    elif name == "temporary":
        mu, sd = np.where((t >= 50) & (t < 70), -0.30, 0.20), 1.0
    elif name == "cost_impaired":
        mu, sd = np.where(t < 60, 0.20, -0.10), 1.0
    elif name == "recovering":
        mu, sd = np.where((t >= 20) & (t < 60), -0.20, 0.20), 1.0
    else:
        raise ValueError(name)
    r = mu + rng.normal(0.0, sd, LENGTH)
    return r, mu > 0


HEALTHY = ("stable", "noisy")
BROKEN = ("gradual", "abrupt", "cost_impaired")
RECOVER = ("temporary", "recovering")
CASES = HEALTHY + BROKEN + RECOVER


def _flags(det: Callable[[list[float]], bool], r: np.ndarray) -> dict[int, bool]:
    out: dict[int, bool] = {}
    for k in range(MIN_N, LENGTH + 1, STEP):
        out[k - 1] = bool(det(list(r[:k])))
    return out


def score_case(det: Callable[[list[float]], bool], case: str, seed: int = 0) -> dict[str, Any]:
    false, delays, missed, reinstate, n_broke, n_rec = 0, [], 0, 0, 0, 0
    for p in range(PATHS):
        r, alive = _case(case, np.random.default_rng(seed * 1000 + p))
        f = _flags(det, r)
        if any(f[i] and alive[i] for i in f):
            false += 1
        dead_idx = np.flatnonzero(~alive)
        if dead_idx.size:
            n_broke += 1
            brk = int(dead_idx[0])
            hits = [i for i in sorted(f) if f[i] and i >= brk]
            if hits:
                delays.append(hits[0] - brk)
            else:
                missed += 1
            back = int(dead_idx[-1]) + 1
            if back < LENGTH:
                n_rec += 1
                late = [i for i in sorted(f) if i >= back + REINSTATE_K]
                if late and f[late[0]]:
                    reinstate += 1
    return {"paths": PATHS, "false_retire": round(false / PATHS, 4),
            "delay": float(np.median(delays)) if delays else None,
            "missed": round(missed / n_broke, 4) if n_broke else None,
            "reinstate_err": round(reinstate / n_rec, 4) if n_rec else None}


def shared_failure(det: Callable[[list[float]], bool], seed: int = 0) -> dict[str, Any]:
    """K sleeves on one common factor, all broken at trade 60."""
    rng = np.random.default_rng(seed + 77)
    common = rng.normal(0.0, 0.7, LENGTH)
    mu = np.where(np.arange(LENGTH) < 60, 0.20, -0.30)
    times = []
    for _ in range(SHARED_K):
        r = mu + common + rng.normal(0.0, 0.7, LENGTH)
        f = _flags(det, r)
        hit = [i for i in sorted(f) if f[i] and i >= 60]
        times.append(hit[0] if hit else None)
    caught = [t for t in times if t is not None]
    return {"sleeves": SHARED_K, "caught": len(caught),
            "distinct_flag_times": len(set(caught)),
            "note": ("one break on a common factor; a detector that retires it as several "
                     "unrelated events counts one fact K times")}


def run_lab(seed: int = 0, deadline: float | None = None) -> dict[str, Any]:
    table: dict[str, Any] = {}
    for name, det in DETECTORS.items():
        row: dict[str, Any] = {}
        for c in CASES:
            if deadline is not None and time.time() > deadline:
                row[c] = {"status": "PENDING", "why": "budget spent"}
                continue
            row[c] = score_case(det, c, seed)
        row["shared_failure"] = (shared_failure(det, seed)
                                 if deadline is None or time.time() <= deadline
                                 else {"status": "PENDING"})
        table[name] = row
    return {"table": table, "verdicts": verdicts(table)}


def _agg(row: dict[str, Any], cases: tuple[str, ...], key: str) -> float | None:
    vals = [row[c][key] for c in cases if isinstance(row.get(c), dict)
            and isinstance(row[c].get(key), (int, float))]
    return float(np.mean(vals)) if vals else None


def verdicts(table: dict[str, Any]) -> dict[str, Any]:
    base = table.get(BASELINE) or {}
    b_delay, b_false = _agg(base, BROKEN, "delay"), _agg(base, HEALTHY, "false_retire")
    b_missed = _agg(base, BROKEN, "missed")
    out: dict[str, Any] = {}
    for name, row in table.items():
        if name == BASELINE:
            continue
        d, f = _agg(row, BROKEN, "delay"), _agg(row, HEALTHY, "false_retire")
        m = _agg(row, BROKEN, "missed")
        if d is None or f is None or m is None or b_delay is None or b_false is None \
                or b_missed is None:
            v = "UNMEASURED"
        elif d < b_delay and f <= b_false and m <= b_missed:
            v = "BEATS_BASELINE"
        elif d >= b_delay and f >= b_false and m >= b_missed:
            v = "LOSES"
        else:
            v = "MIXED"
        out[name] = {"verdict": v, "delay_broken": d, "false_retire_healthy": f,
                     "missed_broken": m, "baseline_missed": b_missed,
                     "baseline_delay": b_delay, "baseline_false_retire": b_false,
                     "reinstate_err": _agg(row, RECOVER, "reinstate_err")}
    return out


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def run(budget_s: float | None = BUDGET_S, force: bool = False, out: Path = OUT
        ) -> dict[str, Any]:
    t0 = time.time()
    if not force and out.exists():
        try:
            prev = json.loads(out.read_text("utf-8"))
            age = t0 - datetime.fromisoformat(prev["generated_utc"]).timestamp()
            if age < EVERY_S and prev.get("status") == "MEASURED":
                return {**prev, "skipped": f"fresh ({age / 3600:.1f}h < {EVERY_S / 3600:.0f}h)"}
        except (OSError, ValueError, KeyError, TypeError):
            pass
    res = run_lab(deadline=(t0 + budget_s) if budget_s else None)
    pending = any(isinstance(c, dict) and c.get("status") == "PENDING"
                  for row in res["table"].values() for c in row.values())
    doc = {"generated_utc": datetime.now(UTC).isoformat(),
           "status": "PARTIAL" if pending else "MEASURED",
           "authority": "none: a measurement. The live ladder stays decay_monitor + one-step "
                        "decay_regime.adjust (one penalty, never multiplied)",
           "baseline": BASELINE, "cases": [*CASES, "shared_failure"],
           "settings": {"length": LENGTH, "window": WINDOW, "step": STEP, "paths": PATHS,
                        "t_dead": T_DEAD, "ewma_halflife": EWMA_HALFLIFE,
                        "reinstate_k": REINSTATE_K},
           "n_detectors_measured": sum(1 for v in res["verdicts"].values()
                                       if v.get("verdict") != "UNMEASURED"),
           "elapsed_s": round(time.time() - t0, 1), **res}
    _write(out, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    doc = run(a.budget_s, a.force)
    print(f"health lab {doc['status']}{' (' + doc['skipped'] + ')' if doc.get('skipped') else ''}")
    for name, v in (doc.get("verdicts") or {}).items():
        print(f"  {name}: {v['verdict']} delay {v['delay_broken']} vs {v['baseline_delay']}, "
              f"false {v['false_retire_healthy']} vs {v['baseline_false_retire']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
