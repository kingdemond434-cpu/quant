"""Stage 2: run the EXACT per-candidate gauntlet over the reconstructed 420, then inject
synthetics with known true Sharpe. READ-ONLY (no DB writes, no report writes)."""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.validation.dsr import expected_max_sharpe, sharpe_ratio
from libs.validation.economic_prior import MechanismType
from libs.validation.reality_check import hansen_spa

PPY = 365.0  # D1 crypto bars: 365 periods/year (annualisation for TRUE-Sharpe reporting)
prepared = pickle.loads(Path("_audit_prepared.pkl").read_bytes())
FAM_ORDER = [f for f in dict.fromkeys(p[0] for p in prepared)]

min_len = min(len(r) for *_x, r in prepared)
matrix = np.column_stack([r[-min_len:] for *_x, r in prepared])
sharpe_estimates = np.array([sharpe_ratio(r) for *_x, r in prepared])
fam_new: dict[str, int] = {}
for f, *_x in prepared:
    fam_new[f] = fam_new.get(f, 0) + 1
fam_sharpes = {
    f: np.array([sharpe_ratio(r) for g, _s, _y, r in prepared if g == f]) for f in fam_new
}
FAMILY_TRIAL_BUDGET = 120


def fam_trials(f: str, prior: dict[str, int]) -> int:
    return max(FAMILY_TRIAL_BUDGET, fam_new[f] + int(prior.get(f, 0)))


# ---------------------------------------------------------------- campaign statistics
pbo_once, rc_once = campaign_pbo_rc(matrix)
spa_once = hansen_spa(matrix)
print("=" * 78)
print(f"CAMPAIGN MATRIX  T={min_len}  N={matrix.shape[1]}")
print(f"  campaign PBO            = {pbo_once.pbo:.4f}   (gate: <=0.50)  "
      f"n_comb={pbo_once.n_combinations}")
print(f"  campaign White's RC p   = {rc_once.p_value:.4f} (gate: <0.05)  stat={rc_once.statistic:.4f}")
print(f"  [ref] Hansen SPA p      = {spa_once.p_value:.4f} (studentized variant, NOT used here)")
print(f"  sharpe_estimates: mean={sharpe_estimates.mean():.5f} sd={sharpe_estimates.std(ddof=1):.5f}")
for f in sorted(fam_new):
    s = fam_sharpes[f]
    n = fam_trials(f, {})
    sr0 = expected_max_sharpe(n, float(s.var(ddof=1)))
    print(f"  family {f:24s} n={fam_new[f]:3d} n_trials={n:4d} "
          f"sd(SR)={s.std(ddof=1):.5f} sr0={sr0:.5f} (ann {sr0*np.sqrt(PPY):.2f})")

# ---------------------------------------------------------------- 420 real candidates
HYP = Hypothesis(family=Family.LIQUIDITY, subtype="probe", symbol="BTCUSDT", params={},
                 mechanism=MechanismType.LIQUIDITY, edge_source="probe",
                 failure_modes=["probe"])
hist: dict[str, int] = {}
survivors = 0
best_dsr = 0.0
for f, sub, sym, r in prepared:
    sh = fam_sharpes[f]
    v = validate(r, hypothesis=HYP, n_trials=fam_trials(f, {}),
                 sharpe_estimates=sh if len(sh) >= 2 else sharpe_estimates,
                 returns_matrix=matrix, pbo=pbo_once, rc=rc_once)
    best_dsr = max(best_dsr, v.metrics.dsr)
    survivors += int(v.survived)
    for g, ok in v.gates.items():
        if not ok:
            hist[g] = hist.get(g, 0) + 1
print("\nPER-GATE REJECT HISTOGRAM over the reconstructed 420 (this code path):")
for g, n in sorted(hist.items(), key=lambda kv: -kv[1]):
    print(f"  {g:20s} {n:4d}/420  ({100*n/420:5.1f}%)")
print(f"  survivors={survivors}   best DSR observed={best_dsr:.4f} (threshold 0.95)")

# marginal analysis: how many die at EACH gate as the SOLE failure
sole: dict[str, int] = {}
for f, sub, sym, r in prepared:
    sh = fam_sharpes[f]
    v = validate(r, hypothesis=HYP, n_trials=fam_trials(f, {}),
                 sharpe_estimates=sh if len(sh) >= 2 else sharpe_estimates,
                 returns_matrix=matrix, pbo=pbo_once, rc=rc_once)
    bad = [g for g, ok in v.gates.items() if not ok]
    if len(bad) == 1:
        sole[bad[0]] = sole.get(bad[0], 0) + 1
print(f"  sole-cause failures: {sole}")


# ---------------------------------------------------------------- the synthetic
def make_synthetic(true_ann_sharpe: float, T: int, seed: int = 7,
                   ann_vol: float = 0.40, df: int = 6) -> np.ndarray:
    """An economically plausible daily net-return stream with a KNOWN true Sharpe.

    Fat-tailed (Student-t, df=6) innovations, ~40% annualised vol (a realistic levered crypto
    sleeve), drift set so E[SR_annual] = true_ann_sharpe.  Costs are already netted out (the drift
    IS the net edge), matching what net_returns() hands the gauntlet.
    """
    rng = np.random.default_rng(seed)
    sd = ann_vol / np.sqrt(PPY)
    z = rng.standard_t(df, size=T)
    z = z / np.sqrt(df / (df - 2.0))          # unit variance
    mu = true_ann_sharpe * sd / np.sqrt(PPY)
    return mu + sd * z


def run_synth(rets: np.ndarray, family: str, inject_into_matrix: bool, label: str,
              prior: dict[str, int] | None = None) -> dict:
    prior = prior or {}
    if inject_into_matrix:
        m = np.column_stack([matrix, rets[-min_len:]])
        p, rc = campaign_pbo_rc(m)
        sh = np.append(fam_sharpes[family], sharpe_ratio(rets))
        nt = fam_trials(family, prior) + 1
    else:
        m, p, rc = matrix, pbo_once, rc_once
        sh = fam_sharpes[family]
        nt = fam_trials(family, prior)
    v = validate(rets, hypothesis=HYP, n_trials=nt, sharpe_estimates=sh,
                 returns_matrix=m, pbo=p, rc=rc)
    failed = [g for g, ok in v.gates.items() if not ok]
    return {"label": label, "survived": v.survived, "failed": failed,
            "dsr": v.metrics.dsr, "pbo": v.metrics.pbo, "reality_p": v.metrics.reality_p,
            "oos_sharpe": v.metrics.oos_sharpe, "n_trials": nt,
            "realised_ann_sr": sharpe_ratio(rets) * np.sqrt(PPY),
            "reported_annual_sharpe": v.metrics.annual_sharpe,
            "fragility": v.metrics.fragility, "capacity": v.metrics.capacity_usd}


print("\n" + "=" * 78)
print("SYNTHETIC SWEEP  (T = %d bars ~ %.1f years of D1)" % (min_len, min_len / PPY))
print("=" * 78)
rows = []
for s in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0]:
    r = make_synthetic(s, min_len)
    for inj in (False, True):
        d = run_synth(r, "liquidity", inj, f"SR={s}")
        rows.append((s, inj, d))
        tag = "in-matrix " if inj else "matrix-as-is"
        print(f"SR_true={s:5.1f} {tag} realisedSR={d['realised_ann_sr']:6.2f} "
              f"DSR={d['dsr']:.4f} PBO={d['pbo']:.3f} RCp={d['reality_p']:.3f} "
              f"{'PASS' if d['survived'] else 'FAIL: ' + ','.join(d['failed'])}")

Path("_audit_rows.pkl").write_bytes(pickle.dumps(rows))
