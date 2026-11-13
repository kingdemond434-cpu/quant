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
The artifact reports the win rate, the summed delta log W and a one-sided exact
sign-test p-value against the plain solve, and a verdict.

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
import time
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np  # noqa: E402

from libs.ops.win_write import write_text_resilient  # noqa: E402
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
PROMOTE_MAX_P = 0.10    # one-sided exact sign-test p-value ceiling for PROMOTE_CANDIDATE
REFIT_EVERY = 10        # walk-forward refits Baum-Welch every k steps; filter runs between


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
    except Exception as exc:  # noqa: BLE001 -- a failed fit is a measured UNMEASURED
        return None, {"status": "UNMEASURED", "why": f"fit_failed: {type(exc).__name__}"}
    return weights_from_model(m, r)


def weights_from_model(m: GaussianHMM, r: np.ndarray) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Run the online filter of an already-fitted model over r and derive next-step weights."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(all="ignore"):
                gamma = m.filter_posterior(r)
    except Exception as exc:  # noqa: BLE001
        return None, {"status": "UNMEASURED", "why": f"filter_failed: {type(exc).__name__}"}
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


def _fit(r: np.ndarray, *, seed: int = 0) -> GaussianHMM | None:
    if r.size < MIN_FIT_N or not np.isfinite(r).all() or float(np.std(r)) < 1e-9:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(all="ignore"):
                return GaussianHMM(N_STATES, n_iter=40, seed=seed).fit(r)
    except Exception:  # noqa: BLE001 -- the weights step reports UNMEASURED
        return None


def solve_pair(r: np.ndarray, model: GaussianHMM | None = None) -> dict[str, Any]:
    """Plain vs conditioned fraction; with `model`, filter with it instead of refitting."""
    plain = growth_fraction(r)
    if model is not None:
        w, info = weights_from_model(model, r)
    else:
        w, info = regime_weights(r)
    cond = plain if w is None else growth_fraction(r, w)
    return {"plain_fraction": plain, "conditioned_fraction": cond, **info}


def walk_forward(r: np.ndarray, *, start: int = MIN_FIT_N,
                 refit_every: int = REFIT_EVERY) -> dict[str, Any]:
    """Expanding-window OOS: solve on r[:t], realise on r[t]. Fallback steps count as ties.

    Baum-Welch is refitted at the first scored step and every `refit_every` steps after it
    (O(n^2/k) not O(n^2)); between refits the online filter runs forward on r[:t] with the
    last fitted parameters, so no step ever sees r[t] before it is realised.
    """
    r = np.asarray(r, dtype="float64")
    lp, lc, measured, refits = 0.0, 0.0, 0, 0
    model: GaussianHMM | None = None
    k = max(1, int(refit_every))
    for t in range(start, r.size):
        if (t - start) % k == 0:
            model = _fit(r[:t])
            refits += 1
        s = solve_pair(r[:t], model) if model is not None else solve_pair(r[:t])
        lp += math.log(max(1e-12, 1.0 + s["plain_fraction"] * r[t]))
        lc += math.log(max(1e-12, 1.0 + s["conditioned_fraction"] * r[t]))
        measured += s["status"] == "MEASURED"
    steps = max(0, r.size - start)
    if steps < MIN_WF_STEPS or measured == 0:
        return {"status": "UNMEASURED", "steps": steps, "measured_steps": measured,
                "refits": refits, "why": "too few out-of-sample steps with a measured fit"}
    return {"status": "MEASURED", "steps": steps, "measured_steps": measured, "refits": refits,
            "plain_logw": round(lp, 6), "conditioned_logw": round(lc, 6),
            "delta_logw": round(lc - lp, 6),
            "conditioned_wins": bool(lc > lp + 1e-12)}


def sign_test_p(wins: int, n: int) -> float | None:
    """One-sided exact binomial P(X >= wins | n, 1/2); None when n == 0."""
    if n <= 0:
        return None
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / 2.0 ** n


def verdict_of(wins: int, n: int, delta_sum: float) -> tuple[str, float | None]:
    p = sign_test_p(wins, n)
    if n < MIN_SCORED_SLEEVES:
        return "UNMEASURED", p
    if (wins / n) >= PROMOTE_WIN_RATE and delta_sum > 0 and p is not None and p <= PROMOTE_MAX_P:
        return "PROMOTE_CANDIDATE", p
    return "NOT_PROMOTE", p


def _key(name: Any) -> str:
    return name if isinstance(name, str) else "|".join(str(x) for x in name)


def evaluate(series: dict[Any, Sequence[float]]) -> dict[str, Any]:
    sleeves: dict[str, Any] = {}
    for name, rs in sorted(series.items(), key=lambda kv: _key(kv[0])):
        r = np.asarray(list(rs), dtype="float64")
        t0 = time.perf_counter()
        wf = walk_forward(r)
        sleeves[_key(name)] = {"n": int(r.size), "solve": solve_pair(r), "walk_forward": wf,
                               "wall_s": round(time.perf_counter() - t0, 4)}
    scored = [s["walk_forward"] for s in sleeves.values() if s["walk_forward"]["status"] == "MEASURED"]
    wins = sum(1 for s in scored if s["conditioned_wins"])
    delta_sum = float(sum(s["delta_logw"] for s in scored))
    win_rate = (wins / len(scored)) if scored else None
    verdict, p = verdict_of(wins, len(scored), delta_sum)
    return {"sleeves": sleeves, "scored_sleeves": len(scored), "wins": wins,
            "win_rate_vs_plain": None if win_rate is None else round(win_rate, 4),
            "delta_logw_sum": round(delta_sum, 6),
            "sign_test_p": None if p is None else round(p, 6),
            "verdict": verdict}


def load_ledger(path: Path = LEDGER) -> dict[Any, list[float]]:
    """Per-series R-multiples in time order. A row carrying `account` is keyed (account,
    sleeve) so accounts are never pooled; rows are deduped on (account, sleeve, signal/open
    time) so one trade written twice is counted once."""
    out: dict[Any, list[float]] = defaultdict(list)
    if not path.exists():
        return {}
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        r = d.get("r_multiple")
        if d.get("sleeve") and isinstance(r, (int, float)) and math.isfinite(r) \
                and not d.get("r_unreconstructible"):
            acct = d.get("account")
            sleeve = str(d["sleeve"])
            stamp = next((str(d[k]) for k in ("signal_time", "open_time", "time")
                          if d.get(k) not in (None, "")), "")
            ident = ("" if acct is None else str(acct), sleeve, stamp)
            if stamp and ident in seen:
                continue
            seen.add(ident)
            key: Any = sleeve if acct is None else (str(acct), sleeve)
            rows.append((str(d.get("time", "") or stamp), _key(key), key, float(r)))
    for _, _, k, r in sorted(rows, key=lambda x: (x[0], x[1])):
        out[k].append(r)
    return dict(out)


def build(path: Path = LEDGER) -> dict[str, Any]:
    series = load_ledger(path)
    res = evaluate(series)
    return {"schema": SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "SHADOW", "auto_promote": False, "live_sizing_changed": False,
            "source": str(path.relative_to(DESK)) if path.is_relative_to(DESK) else str(path),
            "status": "UNMEASURED" if not series else "MEASURED",
            "params": {"n_states": N_STATES, "min_fit_n": MIN_FIT_N, "f_max": F_MAX,
                       "promote_win_rate": PROMOTE_WIN_RATE, "promote_max_p": PROMOTE_MAX_P,
                       "refit_every": REFIT_EVERY,
                       "min_scored_sleeves": MIN_SCORED_SLEEVES},
            "prior_note": "allocator measured regime/macro inputs had not beaten the plain solve "
                          "(14 of 26 windows); a verdict here never changes live sizing",
            **res}


def main() -> int:
    doc = build()
    write_text_resilient(OUT, json.dumps(doc, indent=1, sort_keys=True))
    print(json.dumps({k: doc.get(k) for k in ("status", "scored_sleeves", "win_rate_vs_plain",
                                               "delta_logw_sum", "sign_test_p", "verdict")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
