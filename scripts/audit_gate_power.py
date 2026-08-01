#!/usr/bin/env python3
"""STATISTICAL AUDIT OF THE VALIDATION GAUNTLET -- Type I and Type II, per gate and jointly.

THE QUESTION, asked without assuming the answer: is this gate stack over-conservative,
under-conservative, or near-optimal for maximising long-run compounded return? A gate stack is not
free. Every gate buys a reduction in false positives and pays for it in false negatives, and only
the desk's own objective -- E[log wealth] -- prices that trade. Nobody had measured either side.

METHOD. One cohort is simulated per replication, ``n_true`` of its candidates carrying a genuine
edge and the rest pure noise, then scored through the REAL ``validate()`` with the REAL campaign
statistics. Auditing the live function rather than a reimplementation is the whole point: a
reimplementation would certify a model of the gauntlet, not the gauntlet. Because
``campaign_gate_stats`` is computed once and shared across the cohort's candidates, one expensive
replication yields N verdicts -- which is what makes a Monte Carlo of this size affordable at all.

Every candidate's per-gate booleans AND its continuous statistics are recorded, so Type I error,
power, leave-one-out marginal contributions, ROC curves and calibration all come from the same
pass rather than from separate runs that could disagree.

WHAT IS DELIBERATELY NOT DONE: no threshold is tuned to raise the pass rate. The output is a
measurement. Where it recommends a change, the change must improve expected OUT-OF-SAMPLE
performance -- a higher pass rate on its own is a cost, not a benefit.

    python -u scripts/audit_gate_power.py --n 420 --t 310 --reps 20
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

from libs.autodiscovery.models import Family, Hypothesis  # noqa: E402
from libs.autodiscovery.validation import (  # noqa: E402
    CampaignGates,
    campaign_gate_stats,
    validate,
)
from libs.validation.dsr import sharpe_ratio  # noqa: E402
from libs.validation.economic_prior import MechanismType  # noqa: E402
from libs.validation.positive_control import PPY  # noqa: E402
from libs.validation.stepwise import cscv_candidate_pbo, romano_wolf_stepdown  # noqa: E402

_OUT = Path("reports/gate_power_audit.json")
_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="audit", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="simulated",
    failure_modes=["simulated -- never tradeable"],
)
#: Every gate validate() reports, in the order it reports them.
GATES = ("economic_mechanism", "expected_value", "cpcv", "walk_forward", "dsr", "pbo",
         "reality_check", "capacity", "fragility", "beats_baselines")
#: Annualised vol of a simulated candidate. Sets the scale only -- Sharpe is scale-free -- but a
#: realistic figure keeps the capacity gate's dollar arithmetic in a plausible range.
_ANN_VOL = 0.60


def simulate_returns(
    true_ann_sharpe: float,
    n_obs: int,
    rng: np.random.Generator,
    *,
    common: np.ndarray | None = None,
    rho: float = 0.0,
    ar1: float = 0.0,
    df: float | None = None,
    regime: str = "none",
) -> np.ndarray:
    """A candidate's return stream, with the departures from textbook iid-normal that actually
    change a gate's verdict.

    ``rho``    loading on a shared factor -- this is what makes a cohort's effective number of
               independent tests smaller than its candidate count, and multiplicity corrections
               price the RAW count.
    ``ar1``    serial correlation. Inflates a naive Sharpe's precision and is precisely what the
               purge/embargo in CPCV and the stationary-block bootstrap exist to handle, so a gate
               stack must be audited under it rather than only under white noise.
    ``df``     Student-t degrees of freedom for fat tails; None means Gaussian.
    ``regime`` "none", "decay" (edge halves in the second half), "reverse" (edge flips sign), or
               "late" (edge only appears in the final third). A real alpha is not stationary, and
               a gate stack that only admits stationary alphas rejects most true ones.
    """
    sd = _ANN_VOL / np.sqrt(PPY)
    z = rng.standard_normal(n_obs) if df is None else (
        rng.standard_t(df, n_obs) / np.sqrt(df / (df - 2.0)))
    if ar1:
        # AR(1) with unit-variance innovations scaled so the marginal variance stays 1.
        e = z * np.sqrt(1.0 - ar1**2)
        for i in range(1, n_obs):
            e[i] += ar1 * e[i - 1]
        z = e
    if common is not None and rho:
        z = np.sqrt(rho) * common + np.sqrt(max(0.0, 1.0 - rho)) * z
    # per-period Sharpe is mu/sd, so annualised (mu/sd)*sqrt(PPY) == true_ann_sharpe
    mu = true_ann_sharpe * sd / np.sqrt(PPY)
    drift = np.full(n_obs, mu)
    if regime == "decay":
        drift[n_obs // 2:] *= 0.5
    elif regime == "reverse":
        drift[n_obs // 2:] *= -1.0
    elif regime == "late":
        drift[: 2 * n_obs // 3] = 0.0
        drift[2 * n_obs // 3:] *= 3.0        # same total alpha, concentrated late
    return np.asarray(drift + sd * z)


def simulate_cohort(
    n: int, n_obs: int, rng: np.random.Generator, *, n_true: int, true_ann_sharpe: float,
    rho: float = 0.0, ar1: float = 0.0, df: float | None = None, regime: str = "none",
) -> tuple[np.ndarray, np.ndarray]:
    """Returns ``(matrix[T,N], is_true[N])``. The true alphas are placed FIRST but that is
    irrelevant to every gate here -- none of them reads column order."""
    common = rng.standard_normal(n_obs) if rho else None
    cols, flags = [], np.zeros(n, dtype=bool)
    for k in range(n):
        is_true = k < n_true
        flags[k] = is_true
        cols.append(simulate_returns(
            true_ann_sharpe if is_true else 0.0, n_obs, rng,
            common=common, rho=rho, ar1=ar1, df=df, regime=(regime if is_true else "none")))
    return np.column_stack(cols), flags


def effective_n_tests(matrix: np.ndarray) -> dict[str, float]:
    """How many INDEPENDENT tests the cohort really represents.

    Multiplicity corrections deflate by the number of trials, and every one of them here is handed
    the RAW candidate count. When candidates are correlated -- and 420 variants over one universe
    in one era are heavily correlated -- the raw count overstates the true multiplicity, so the
    deflation is too harsh by a factor that nobody has ever measured on this desk.

    Two standard estimators, reported together because they disagree in informative ways:
    ``kaiser`` counts eigenvalues above 1 (components carrying more than one variable's worth of
    variance) and ``participation`` is the participation ratio (sum L)^2 / sum L^2, which is
    smooth and does not depend on a cutoff.
    """
    m = np.asarray(matrix, dtype="float64")
    if m.shape[1] < 2:
        return {"n_raw": float(m.shape[1]), "kaiser": 1.0, "participation": 1.0, "li_ji": 1.0}
    c = np.corrcoef(m, rowvar=False)
    c = np.nan_to_num(c, nan=0.0)
    lam = np.linalg.eigvalsh(c)
    lam = np.clip(lam, 0.0, None)
    n_raw = float(m.shape[1])
    part = float(lam.sum() ** 2 / np.sum(lam**2)) if np.sum(lam**2) > 0 else n_raw
    kaiser = float(np.sum(lam > 1.0))
    # Li & Ji (2005): sum over eigenvalues of [I(L>=1) + (L - floor(L))]
    li_ji = float(np.sum((lam >= 1.0).astype(float) + (lam - np.floor(lam))))
    return {"n_raw": n_raw, "kaiser": kaiser, "participation": part, "li_ji": min(li_ji, n_raw)}


def campaign_stats_fast(matrix: np.ndarray) -> CampaignGates:
    """The per-candidate campaign statistics WITHOUT the legacy campaign constants.

    Pure cost control, and it changes no verdict -- which is asserted, not assumed, by
    ``test_fast_campaign_path_is_verdict_identical``. ``campaign_gate_stats`` also computes
    ``campaign_pbo_rc``, whose classic PBO enumerates C(16,8)=12,870 splits unvectorised and costs
    >100s at N=420 -- roughly 25x everything else in this audit combined. The per-candidate path
    reads ``cscv`` and ``stepdown`` only; ``legacy_pbo``/``legacy_rc`` are consumed exclusively by
    the legacy branch of validate(), which is selected by passing pbo=/rc= instead of campaign=.

    Skipping it turns a ~2-minute replication into a ~5-second one, which is the difference
    between a Monte Carlo with usable confidence intervals and a handful of anecdotes.
    """
    return CampaignGates(cscv=cscv_candidate_pbo(matrix),
                         stepdown=romano_wolf_stepdown(matrix),
                         legacy_pbo=None, legacy_rc=None)


def score_cohort(matrix: np.ndarray, flags: np.ndarray, *, n_trials: int | None = None,
                 per_candidate: bool = True, fast: bool = True) -> list[dict[str, Any]]:
    """Every candidate's per-gate verdict AND continuous statistics, from the REAL validate().

    Campaign statistics are computed once for the whole cohort and shared, which is both what the
    live campaign does and what makes the replication affordable.
    """
    gates = campaign_stats_fast(matrix) if (fast and per_candidate) \
        else campaign_gate_stats(matrix)
    if gates is None:
        raise RuntimeError("campaign_gate_stats returned None")
    sh = np.array([sharpe_ratio(matrix[:, i]) for i in range(matrix.shape[1])])
    n_tr = int(n_trials if n_trials is not None else matrix.shape[1])
    rows: list[dict[str, Any]] = []
    for k in range(matrix.shape[1]):
        kw: dict[str, Any] = {"campaign": gates, "column": k} if per_candidate else {
            "pbo": gates.legacy_pbo, "rc": gates.legacy_rc}
        v = validate(matrix[:, k], hypothesis=_HYP, n_trials=n_tr, sharpe_estimates=sh,
                     returns_matrix=matrix, **kw)
        rows.append({
            "is_true": bool(flags[k]),
            "survived": bool(v.survived),
            "gates": {g: bool(v.gates.get(g, True)) for g in GATES},
            "dsr": float(v.metrics.dsr),
            "pbo": float(v.metrics.pbo),
            "reality_p": float(v.metrics.reality_p),
            "oos_sharpe": float(v.metrics.oos_sharpe),
            "realised_ann_sharpe": float(sharpe_ratio(matrix[:, k]) * np.sqrt(PPY)),
        })
    return rows


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- correct at the 0 and 1 boundaries, where this audit lives and
    where the normal approximation gives a zero-width interval and a false sense of precision."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1.0 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(max(0.0, p * (1 - p) / n + z**2 / (4 * n**2))) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Type I, power, per-gate blocking rates, and the leave-one-out marginals."""
    nulls = [r for r in rows if not r["is_true"]]
    trues = [r for r in rows if r["is_true"]]

    def rate(sub: list[dict[str, Any]], key: str) -> dict[str, Any]:
        k = sum(1 for r in sub if r[key])
        lo, hi = _wilson(k, len(sub))
        return {"k": k, "n": len(sub), "rate": (k / len(sub)) if sub else None,
                "ci95": [lo, hi]}

    per_gate = {}
    for g in GATES:
        # A gate's Type I contribution is how often it PASSES a null (lets noise through); its
        # Type II contribution is how often it BLOCKS a true alpha.
        per_gate[g] = {
            "passes_null": rate([{**r, "_": r["gates"][g]} for r in nulls], "_"),
            "blocks_true": {**rate([{**r, "_": not r["gates"][g]} for r in trues], "_")},
        }

    # LEAVE-ONE-OUT: what the pipeline would do without each gate. This is the marginal
    # contribution question -- a gate that costs power without buying false-positive reduction is
    # pure loss, and only this comparison can show it.
    loo = {}
    for g in GATES:
        others = [x for x in GATES if x != g]
        fp = sum(1 for r in nulls if all(r["gates"][o] for o in others))
        tp = sum(1 for r in trues if all(r["gates"][o] for o in others))
        base_fp = sum(1 for r in nulls if r["survived"])
        base_tp = sum(1 for r in trues if r["survived"])
        loo[g] = {
            "fpr_without": (fp / len(nulls)) if nulls else None,
            "power_without": (tp / len(trues)) if trues else None,
            "delta_fpr": ((fp - base_fp) / len(nulls)) if nulls else None,
            "delta_power": ((tp - base_tp) / len(trues)) if trues else None,
        }

    # SOLE BLOCKER: among true alphas the pipeline killed, which single gate did it alone? A gate
    # that is never the sole blocker is redundant; one that usually is, is the binding constraint.
    sole: dict[str, int] = {}
    for r in trues:
        failed = [g for g in GATES if not r["gates"][g]]
        if len(failed) == 1:
            sole[failed[0]] = sole.get(failed[0], 0) + 1
    return {
        "n_null": len(nulls), "n_true": len(trues),
        "type_i_joint": rate(nulls, "survived"),
        "power_joint": rate(trues, "survived"),
        "per_gate": per_gate,
        "leave_one_out": loo,
        "sole_blocker_of_true_alpha": dict(sorted(sole.items(), key=lambda x: -x[1])),
    }


def calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Are the corrections SIZED correctly? Under the null a p-value must be ~uniform and a
    posterior-style score like DSR must exceed 0.95 about 5% of the time. A correction that is
    far tighter than its nominal level is over-conservative BY CONSTRUCTION rather than by
    configuration, and no threshold change fixes that -- it is the wrong instrument."""
    nulls = [r for r in rows if not r["is_true"]]
    if not nulls:
        return {}
    dsr = np.array([r["dsr"] for r in nulls])
    rcp = np.array([r["reality_p"] for r in nulls])
    pbo = np.array([r["pbo"] for r in nulls])
    return {
        "dsr_nominal_fpr": 0.05,
        "dsr_realised_fpr": float(np.mean(dsr >= 0.95)),
        "dsr_quantiles": {q: float(np.quantile(dsr, q)) for q in (0.5, 0.9, 0.95, 0.99)},
        "reality_p_nominal_fpr": 0.05,
        "reality_p_realised_fpr": float(np.mean(rcp <= 0.05)),
        "reality_p_mean_should_be_0.5_if_uniform": float(np.mean(rcp)),
        "reality_p_quantiles": {q: float(np.quantile(rcp, q)) for q in (0.05, 0.1, 0.5, 0.9)},
        "pbo_realised_fpr_at_0.5": float(np.mean(pbo <= 0.5)),
        "pbo_mean": float(np.mean(pbo)),
    }


def roc(rows: list[dict[str, Any]], key: str, *, higher_is_better: bool) -> list[dict[str, float]]:
    """ROC for one continuous statistic, so a gate's DISCRIMINATION is separated from its
    THRESHOLD. A statistic with good AUC and a badly-placed threshold is a configuration problem;
    one with AUC ~0.5 is uninformative at every threshold and no re-tuning will save it."""
    nulls = np.array([r[key] for r in rows if not r["is_true"]])
    trues = np.array([r[key] for r in rows if r["is_true"]])
    if not len(nulls) or not len(trues):
        return []
    cuts = np.unique(np.concatenate([nulls, trues]))
    out = []
    for c in cuts:
        tpr = float(np.mean(trues >= c) if higher_is_better else np.mean(trues <= c))
        fpr = float(np.mean(nulls >= c) if higher_is_better else np.mean(nulls <= c))
        out.append({"cut": float(c), "tpr": tpr, "fpr": fpr})
    return out


def auc(rows: list[dict[str, Any]], key: str, *, higher_is_better: bool) -> float | None:
    """Mann-Whitney AUC: P(a true alpha scores better than a null one)."""
    nulls = np.array([r[key] for r in rows if not r["is_true"]])
    trues = np.array([r[key] for r in rows if r["is_true"]])
    if not len(nulls) or not len(trues):
        return None
    gt = float(np.mean(trues[:, None] > nulls[None, :]))
    eq = float(np.mean(trues[:, None] == nulls[None, :]))
    a = gt + 0.5 * eq
    return a if higher_is_better else 1.0 - a


def _merge(all_rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [r for rep in all_rows for r in rep]


def run_condition(*, n: int, n_obs: int, true_sr: float, n_true: int, reps: int, seed0: int,
                  rho: float = 0.0, ar1: float = 0.0, df: float | None = None,
                  regime: str = "none", n_trials: int | None = None,
                  per_candidate: bool = True, verbose: bool = True) -> dict[str, Any]:
    reps_rows, neff = [], []
    for i in range(reps):
        rng = np.random.default_rng(seed0 + 7919 * i)
        m, flags = simulate_cohort(n, n_obs, rng, n_true=n_true, true_ann_sharpe=true_sr,
                                   rho=rho, ar1=ar1, df=df, regime=regime)
        t0 = time.time()
        reps_rows.append(score_cohort(m, flags, n_trials=n_trials, per_candidate=per_candidate))
        neff.append(effective_n_tests(m))
        if verbose:
            print(f"    rep {i + 1}/{reps} [{time.time() - t0:5.1f}s]", flush=True)
    rows = _merge(reps_rows)
    s = summarise(rows)
    s["condition"] = {"n": n, "t": n_obs, "true_sr": true_sr, "n_true": n_true, "reps": reps,
                      "rho": rho, "ar1": ar1, "df": df, "regime": regime,
                      "n_trials": n_trials or n, "path": "per_candidate" if per_candidate
                      else "legacy"}
    s["effective_n_tests"] = {k: float(np.mean([d[k] for d in neff])) for k in neff[0]}
    # THE ESTIMATOR'S OWN FLOOR, measured on an INDEPENDENT cohort of the same shape. When T < N
    # the sample correlation matrix has rank <= T, so every eigenvalue-based N_eff is biased below
    # N even with zero true dependence: at N=420, T=310 the participation ratio reads ~179 on
    # perfectly independent columns. Reporting the raw figure alone would manufacture a finding
    # ("only 179 independent tests!") out of an estimation artifact. The interpretable quantity is
    # the RATIO of the measured value to this baseline.
    rng_b = np.random.default_rng(seed0 + 104729)
    base_m, _ = simulate_cohort(n, n_obs, rng_b, n_true=0, true_ann_sharpe=0.0, rho=0.0)
    s["effective_n_tests_independent_baseline"] = effective_n_tests(base_m)
    s["effective_n_tests_ratio_vs_baseline"] = {
        k: (s["effective_n_tests"][k] / v if v else None)
        for k, v in s["effective_n_tests_independent_baseline"].items()}
    s["calibration"] = calibration(rows)
    s["auc"] = {"dsr": auc(rows, "dsr", higher_is_better=True),
                "reality_p": auc(rows, "reality_p", higher_is_better=False),
                "pbo": auc(rows, "pbo", higher_is_better=False),
                "oos_sharpe": auc(rows, "oos_sharpe", higher_is_better=True)}
    return s


#: The campaign the desk's 0-of-420 record was measured on -- every study is anchored to it.
_BASE_N, _BASE_T = 420, 310
_N_TRUE = 20                        # ~5% of the cohort genuinely has an edge; a realistic prior


def _studies(reps: int, n_true: int) -> dict[str, list[dict[str, Any]]]:
    """Every condition this audit runs, as data.

    Each study isolates ONE candidate explanation for the desk's 0-survivor record, so the
    bottleneck question is answered by comparison rather than by argument: if lengthening the
    sample moves power and widening the cohort does not, the bottleneck is history, not campaign
    size -- and the reverse is equally decidable.
    """
    base = {"reps": reps, "n_true": n_true}
    return {
        # A. the power curve at the campaign's OWN shape -- the headline number
        "power_curve": [{**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": sr}
                        for sr in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0)],
        # B. sample length, holding cohort size fixed
        "history_length": [{**base, "n": _BASE_N, "n_obs": t, "true_sr": 2.0}
                           for t in (310, 620, 1250, 2500)],
        # C. campaign size, holding history fixed
        "campaign_size": [{**base, "n": n, "n_obs": _BASE_T, "true_sr": 2.0,
                           "n_true": max(2, int(n * n_true / _BASE_N))}
                          for n in (30, 100, 420)],
        # D. correlation -- the effective-multiplicity question
        "correlation": [{**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "rho": r}
                        for r in (0.0, 0.3, 0.6, 0.9)],
        # E. departures from iid-normal that a real alpha actually exhibits
        "realism": [
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "ar1": 0.2},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "df": 4.0},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "decay"},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "reverse"},
            {**base, "n": _BASE_N, "n_obs": _BASE_T, "true_sr": 3.0, "regime": "late"},
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="power_curve",
                    help="power_curve|history_length|campaign_size|correlation|realism|all")
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--n-true", type=int, default=_N_TRUE)
    ap.add_argument("--seed0", type=int, default=90210)
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args()

    studies = _studies(args.reps, args.n_true)
    names = list(studies) if args.study == "all" else [args.study]
    out: dict[str, Any] = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "base_shape": {"n": _BASE_N, "t": _BASE_T}, "studies": {}}
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    for name in names:
        out["studies"][name] = []
        for spec in studies[name]:
            s = dict(spec)
            if s["true_sr"] <= 0:
                s["n_true"] = 0
            print(f"== {name}: {s} ==", flush=True)
            out["studies"][name].append(run_condition(seed0=args.seed0, **s))
            # CHECKPOINT per condition: a long sweep that dies at 90% must not discard the 90%.
            p.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
