"""HMM regime posterior as a conditioning input to the E[log W] solve -- SHADOW ONLY.

    python research/hmm_regime_elog_shadow.py

Pass-coverage item 54. Per sleeve, from the desk's own realised trade ledger
(`data/live_ledger.jsonl`, R-multiples), this computes two growth-optimal risk
fractions:

  plain        argmax_f  mean_s log(1 + f * r_s)              (every sample weighted equally)
  conditioned  argmax_f  sum_s w_s log(1 + f * r_s) / sum w   where
               w_s = sum_k q_k * gamma_{s,k} / occupancy_k,
               gamma = the ONLINE FILTERED posterior P(state_s | r_1..s) of a
               Gaussian HMM (`libs/regime/hmm.py`, Baum-Welch) and q = the
               one-step-ahead predicted state distribution (filter at T times A).

Each world/sample's return is weighted by the filtered state probability; a
degenerate or insufficient fit (too few trades, a state with ~no occupancy,
non-finite parameters, two indistinguishable states) falls back to the plain
solve with status UNMEASURED -- absence never resolves to a clean verdict.

It is then scored honestly OUT OF SAMPLE: an expanding walk-forward in which
both fractions are solved on trades 1..t and realised on trade t+1. The sleeve
"wins" when its conditioned cumulative realised log-growth beats the plain.
The artifact reports the win rate against the plain solve and a verdict.

AUTHORITY: NONE. Nothing here touches the gateway, decision_core, the
allocator's output, the promoter, rails or any signed file. `auto_promote` is
always False; a PROMOTE_CANDIDATE verdict is a recommendation for the
principal, not a change to live sizing. (The allocator measured that
regime/macro inputs had not yet beaten the plain solve: 14 of 26 windows.)
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np  # noqa: E402

from libs.regime.hmm import GaussianHMM  # noqa: E402

DESK = Path(__file__).resolve().parent.parent
LEDGER = DESK / "data" / "live_ledger.jsonl"
OUT = DESK / "reports" / "hmm_regime_elog_shadow.json"

SCHEMA = "hmm_regime_elog_shadow/1"
N_STATES = 2
MIN_FIT_N = 40          # fewer trades than this: UNMEASURED, plain solve stands
MIN_OCCUPANCY = 0.05    # a state holding less than this share of mass is degenerate
MIN_SEPARATION = 0.25   # |mu_a - mu_b| / pooled sd below this: states indistinguishable
F_MAX = 0.25            # risk fraction grid ceiling (fraction of equity at risk per 1R)
GRID = np.linspace(0.0, F_MAX, 101)
MIN_WF_STEPS = 10       # walk-forward realisations needed before a sleeve is scored
MIN_SCORED_SLEEVES = 3  # sleeves needed before any verdict other than UNMEASURED
PROMOTE_WIN_RATE = 0.6  # conditioned must beat the plain solve on at least this share


def growth_fraction(r: np.ndarray, w: np.ndarray | None = None) -> float:
    """Grid argmax of the (weighted) mean log(1 + f r); infeasible fractions excluded."""
    r = np.asarray(r, dtype="float64")
    if r.size == 0:
        return 0.0
    w = np.ones_like(r) if w is None else np.asarray(w, dtype="float64")
    w = w / w.sum()
    best_f, best_g = 0.0, 0.0
    for f in GRID[1:]:
        x = 1.0 + f * r
        if np.any(x <= 0):
            break
        g = float(np.sum(w * np.log(x)))
        if g > best_g:
            best_f, best_g = float(f), g
    return best_f


def regime_weights(r: np.ndarray, *, seed: int = 0) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Fit the HMM on r and return per-sample weights for the NEXT step, or (None, why)."""
    r = np.asarray(r, dtype="float64")
    if r.size < MIN_FIT_N:
        return None, {"status": "UNMEASURED", "why": f"insufficient: n={r.size} < {MIN_FIT_N}"}
    if not np.isfinite(r).all() or float(np.std(r)) < 1e-9:
        return None, {"status": "UNMEASURED", "why": "degenerate: constant or non-finite series"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(all="ignore"):
                m = GaussianHMM(N_STATES, n_iter=40, seed=seed).fit(r)
                gamma = m.filter_posterior(r)
    except Exception as exc:  # noqa: BLE001 -- a failed fit is a measured UNMEASURED
        return None, {"status": "UNMEASURED", "why": f"fit_failed: {type(exc).__name__}"}
    params = np.concatenate([m.means.ravel(), m.vars.ravel(), m.transmat.ravel(), gamma.ravel()])
    if not np.isfinite(params).all():
        return None, {"status": "UNMEASURED", "why": "degenerate: non-finite fit"}
    occ = gamma.mean(axis=0)
    if float(occ.min()) < MIN_OCCUPANCY:
        return None, {"status": "UNMEASURED", "why": f"degenerate: occupancy {occ.round(3).tolist()}"}
    mu = m.means.ravel()
    sep = float(abs(mu[0] - mu[1]) / math.sqrt(float(np.mean(m.vars.ravel())) + 1e-12))
    if sep < MIN_SEPARATION:
        return None, {"status": "UNMEASURED", "why": f"degenerate: separation {sep:.3f}"}
    q = gamma[-1] @ m.transmat
    w = (gamma / occ) @ q
    return w, {"status": "MEASURED", "means": mu.round(4).tolist(),
               "occupancy": occ.round(4).tolist(), "separation": round(sep, 4),
               "next_state_prob": np.asarray(q).round(4).tolist()}


def solve_pair(r: np.ndarray) -> dict[str, Any]:
    plain = growth_fraction(r)
    w, info = regime_weights(r)
    cond = plain if w is None else growth_fraction(r, w)
    return {"plain_fraction": plain, "conditioned_fraction": cond, **info}


def walk_forward(r: np.ndarray, *, start: int = MIN_FIT_N) -> dict[str, Any]:
    """Expanding-window OOS: solve on r[:t], realise on r[t]. Fallback steps count as ties."""
    r = np.asarray(r, dtype="float64")
    lp, lc, measured = 0.0, 0.0, 0
    for t in range(start, r.size):
        s = solve_pair(r[:t])
        lp += math.log(max(1e-12, 1.0 + s["plain_fraction"] * r[t]))
        lc += math.log(max(1e-12, 1.0 + s["conditioned_fraction"] * r[t]))
        measured += s["status"] == "MEASURED"
    steps = max(0, r.size - start)
    if steps < MIN_WF_STEPS or measured == 0:
        return {"status": "UNMEASURED", "steps": steps, "measured_steps": measured,
                "why": "too few out-of-sample steps with a measured fit"}
    return {"status": "MEASURED", "steps": steps, "measured_steps": measured,
            "plain_logw": round(lp, 6), "conditioned_logw": round(lc, 6),
            "conditioned_wins": bool(lc > lp + 1e-12)}


def evaluate(series: dict[str, Sequence[float]]) -> dict[str, Any]:
    sleeves: dict[str, Any] = {}
    for name, rs in sorted(series.items()):
        r = np.asarray(list(rs), dtype="float64")
        sleeves[name] = {"n": int(r.size), "solve": solve_pair(r), "walk_forward": walk_forward(r)}
    scored = [s["walk_forward"] for s in sleeves.values() if s["walk_forward"]["status"] == "MEASURED"]
    wins = sum(1 for s in scored if s["conditioned_wins"])
    win_rate = (wins / len(scored)) if scored else None
    if len(scored) < MIN_SCORED_SLEEVES:
        verdict = "UNMEASURED"
    elif win_rate is not None and win_rate >= PROMOTE_WIN_RATE:
        verdict = "PROMOTE_CANDIDATE"
    else:
        verdict = "NOT_PROMOTE"
    return {"sleeves": sleeves, "scored_sleeves": len(scored), "wins": wins,
            "win_rate_vs_plain": None if win_rate is None else round(win_rate, 4),
            "verdict": verdict}


def load_ledger(path: Path = LEDGER) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    if not path.exists():
        return {}
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        r = d.get("r_multiple")
        if d.get("sleeve") and isinstance(r, (int, float)) and math.isfinite(r) \
                and not d.get("r_unreconstructible"):
            rows.append((str(d.get("time", "")), str(d["sleeve"]), float(r)))
    for _, s, r in sorted(rows):
        out[s].append(r)
    return dict(out)


def build(path: Path = LEDGER) -> dict[str, Any]:
    series = load_ledger(path)
    res = evaluate(series)
    return {"schema": SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "SHADOW", "auto_promote": False, "live_sizing_changed": False,
            "source": str(path.relative_to(DESK)) if path.is_relative_to(DESK) else str(path),
            "status": "UNMEASURED" if not series else "MEASURED",
            "params": {"n_states": N_STATES, "min_fit_n": MIN_FIT_N, "f_max": F_MAX,
                       "promote_win_rate": PROMOTE_WIN_RATE,
                       "min_scored_sleeves": MIN_SCORED_SLEEVES},
            "prior_note": "allocator measured regime/macro inputs had not beaten the plain solve "
                          "(14 of 26 windows); a verdict here never changes live sizing",
            **res}


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(OUT)
    print(json.dumps({k: doc[k] for k in ("status", "scored_sleeves", "win_rate_vs_plain",
                                           "verdict")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
