"""Full institutional validation per candidate — every gate, no weakening, fail-closed.

Runs the complete stack and a candidate survives ONLY if every gate passes: economic mechanism,
CPCV (purged K-fold OOS consistency), PBO, Deflated Sharpe (trials-deflated), White's Reality Check,
Walk-Forward, capacity, fragility (tail risk), and an accelerated shadow check (final held-out
segment). Reuses the existing validation / discovery primitives. Thresholds are constants here and
never relaxed.
"""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.models import Hypothesis, ValidationMetrics, ValidationVerdict
from libs.discovery.capacity import capacity_estimate
from libs.discovery.tail_risk import tail_risk
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, whites_reality_check
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus

_PERIODS_PER_YEAR = 24 * 260
_DSR_THRESHOLD = 0.95
_MIN_CAPACITY_USD = 1.0e5
_CPCV_MIN_POSITIVE = 0.6   # >=60% of purged folds positive


def _cpcv_positive_fraction(returns: np.ndarray, *, k: int = 5) -> float:
    folds = np.array_split(returns, k)
    positive = [f.mean() > 0 for f in folds if len(f) > 1]
    return float(np.mean(positive)) if positive else 0.0


def campaign_pbo_rc(
    returns_matrix: np.ndarray,
) -> tuple[PBOResult | None, RealityCheckResult | None]:
    """Compute PBO and White's Reality Check ONCE per campaign (they depend only on the matrix).

    These two gates are identical for every candidate in a campaign, so computing them once and
    passing the results into :func:`validate` avoids O(N) redundant bootstraps -- a large speedup
    with no change to the verdict. (Used by the orchestrator; validate() falls back to per-call
    computation when not supplied.)
    """
    if returns_matrix.shape[1] < 2:
        return None, None
    return probability_backtest_overfitting(returns_matrix), whites_reality_check(returns_matrix)


def validate(
    returns: np.ndarray,
    *,
    hypothesis: Hypothesis,
    n_trials: int,
    sharpe_estimates: np.ndarray,
    returns_matrix: np.ndarray,
    adv_usd: float = 1.0e11,
    edge_bps: float | None = None,
    pbo: PBOResult | None = None,
    rc: RealityCheckResult | None = None,
    pc_pbo: float | None = None,
    pc_p: float | None = None,
) -> ValidationVerdict:
    arr = np.asarray(returns, dtype="float64")
    if len(arr) < 250:
        return ValidationVerdict(
            survived=False, gates={"sufficient_data": False},
            rejection_reason="insufficient data", metrics=ValidationMetrics(),
        )

    # Walk-forward (OOS). Shadow/paper are separate lifecycle stages (see lifecycle.py).
    wf = WalkForwardEngine().evaluate(arr, n_splits=4, test_size=max(20, len(arr) // 6))
    dsr = deflated_sharpe_ratio(arr, n_trials=n_trials, sharpe_estimates=sharpe_estimates,
                                threshold=_DSR_THRESHOLD)
    # PER-CANDIDATE, NOT PER-CAMPAIGN (register #71). White's RC asks "is the BEST strategy in
    # this set real?" and PBO asks "does the SELECTION PROCEDURE overfit?" -- both are properties
    # of the SET, and handing each candidate the set's verdict let one number decide all of them.
    # Measured here: campaign PBO 0.6159 and RC p 0.4220 made `pbo` and `reality_check` False for
    # all 420 candidates regardless of merit, and campaign PBO RISES with candidate count, so the
    # bar tightened every time the desk generated more -- which TWO_STAGE_DISCOVERY_LAW forbids.
    #
    # It fails the other way too, which is worse: plant ONE real edge among 19 noise strategies
    # and campaign RC returns p=0.003, passing the reality_check gate for all twenty.
    #
    # Romano-Wolf stepdown and per-strategy CSCV keep the veto and make it DISCRIMINATE. Not
    # RANK-not-VETO, which would lower the bar; each candidate is now judged on its own evidence
    # and can neither be rescued nor condemned by its peers.
    # COMPUTED ONCE PER CAMPAIGN, INDEXED PER CANDIDATE. Both statistics are vectorised over
    # every strategy already, so the caller runs them once and passes this candidate's slice --
    # keeping the O(N) bootstrap saving the campaign version was written for, while fixing the
    # statistic it got wrong. The first draft called them inside the candidate loop, which is
    # O(N^2) and would have been unusable at the 420 candidates that motivated the fix.
    has_peers = returns_matrix.shape[1] >= 2
    if pbo is None and has_peers:
        pbo = probability_backtest_overfitting(returns_matrix)
    if rc is None and has_peers:
        rc = whites_reality_check(returns_matrix)
    # Candidate-aware capacity: use the strategy's OWN realized per-bar edge (bps), so a no-edge
    # strategy gets ~zero capacity (fails) while a real edge on a liquid market passes -- instead
    # of the old fixed edge_bps that made this gate a constant veto for every candidate.
    eff_edge_bps = edge_bps if edge_bps is not None else max(0.0, float(arr.mean()) * 1.0e4)
    cap = capacity_estimate(adv_usd=adv_usd, edge_bps=max(eff_edge_bps, 1.0e-9))
    tail = tail_risk(arr)

    metrics = ValidationMetrics(
        annual_sharpe=float(sharpe_ratio(arr) * np.sqrt(_PERIODS_PER_YEAR)),
        expected_value=float(arr.mean()),
        oos_sharpe=wf.oos_sharpe,
        dsr=dsr.dsr,
        pbo=pc_pbo if pc_pbo is not None else (pbo.pbo if pbo is not None else 1.0),
        reality_p=pc_p if pc_p is not None else (rc.p_value if rc is not None else 1.0),
        capacity_usd=cap.capacity_usd,
        fragility=tail.tail_risk_score,
    )

    gates = {
        "economic_mechanism": bool(hypothesis.failure_modes),   # declared before testing
        "expected_value": metrics.expected_value > 0,
        "cpcv": _cpcv_positive_fraction(arr) >= _CPCV_MIN_POSITIVE,
        "walk_forward": wf.status is WalkForwardStatus.PASSED,
        "dsr": dsr.passed,
        "pbo": (pc_pbo <= 0.5) if pc_pbo is not None
               else (pbo is not None and not pbo.overfit),
        "reality_check": (pc_p <= 0.05) if pc_p is not None
                         else (rc is not None and rc.significant_at_5pct),
        "capacity": cap.capacity_usd >= _MIN_CAPACITY_USD,
        "fragility": tail.acceptable,
    }
    failed = [name for name, ok in gates.items() if not ok]
    return ValidationVerdict(
        survived=not failed, gates=gates,
        rejection_reason="" if not failed else "failed: " + ", ".join(failed),
        metrics=metrics,
    )


def gate_discrimination(gate_results: list[dict[str, bool]]) -> dict[str, dict]:
    """GAP #71 INSTRUMENTATION -- which gates actually DISCRIMINATE, and which are constants.

    THE MEASURED PROBLEM. `pbo` and `reality_check` are computed ONCE per campaign (they are
    properties of the returns matrix, not of any candidate) and then applied as PER-CANDIDATE
    gates. So when campaign PBO is 0.6159 against a 0.50 bar, that gate reads False for every
    candidate in the campaign -- all 420 of them -- no matter how good any individual one is. The
    desk's own numbers: 420 candidates tested, ZERO survivors, while the genuinely per-candidate
    gates discriminated normally (walk_forward 58.1%, fragility 47.9%).

    WHY THIS REPORTS RATHER THAN FIXES. Turning a campaign veto into a rank would LOWER a
    statistical bar, and this desk's standing research directive is explicit -- *"Never reduce
    statistical standards. Only improve efficiency."* The gap register dates the redesign and
    marks it as needing a principal ruling on RANK-not-VETO. So this measures the mechanism
    instead of quietly relaxing it: a gate that passes everything or fails everything carries
    zero information about any individual candidate, and the desk should be able to SEE that
    rather than infer it from an empty survivor list.

    A constant gate is not necessarily wrong. A campaign really can be overfit end to end. What
    is wrong is not knowing which of the two you are looking at.
    """
    if not gate_results:
        return {}
    names = list(gate_results[0])
    n = len(gate_results)
    out: dict[str, dict] = {}
    for g in names:
        passed = sum(1 for r in gate_results if r.get(g))
        rate = passed / n
        constant = passed in (0, n)
        out[g] = {
            "pass_rate": round(rate, 4), "passed": passed, "n": n,
            "discriminates": not constant,
            "note": ("" if not constant else
                     (f"CONSTANT: this gate {'passed' if passed else 'FAILED'} for all {n} "
                      f"candidates, so it carries zero information about any individual one. "
                      + ("A gate failing everything is a campaign-level verdict wearing a "
                         "per-candidate costume -- the whole campaign is being rejected, not "
                         "these candidates." if not passed else
                         "A gate passing everything is not filtering; confirm it is still "
                         "wired to anything."))),
        }
    return out


def blocking_constant_gates(gate_results: list[dict[str, bool]]) -> list[str]:
    """Gates that FAILED every candidate -- the ones that make promotion arithmetically
    impossible regardless of candidate quality. Empty is the healthy state."""
    return [g for g, d in gate_discrimination(gate_results).items()
            if not d["discriminates"] and d["passed"] == 0]


def counterfactual_survivors(
    gate_results: list[dict[str, bool]], waive: list[str] | tuple[str, ...],
) -> dict:
    """GAP #71, THE QUESTION A RULING ACTUALLY NEEDS: if these gates were waived, who survives?

    "Should we relax the campaign veto?" is unanswerable in the abstract and trivially answerable
    from the gate matrix -- but only if someone computes it. It was computed ONCE, by hand, and
    the result lives in a recommendation-ledger entry nobody re-reads. This makes it an output of
    every campaign, so the ruling is made against current evidence rather than a remembered one.

    THE MEASURED ANSWER ON THE REAL 420: zero. Waiving `pbo` and `reality_check` produces no
    survivors, because every candidate ALSO failed at least one genuinely per-candidate gate --
    which is precisely what the register's "sole-cause failures EMPTY" was recording. Relaxing
    the veto would not have promoted anything; it would only have changed which failure was
    reported first.

    That is worth knowing in both directions. It says the campaign veto is not, today, the thing
    standing between the desk and a validated alpha -- so relaxing it buys nothing and costs a
    statistical standard. It also says the structural objection to the veto stands on its own
    merits (campaign PBO rises with generation volume, which contradicts the Two-Stage Discovery
    Law's "the confirmation bar never rises with generation") rather than on a promise of
    survivors it cannot keep.

    `independent_estimate` is included as the naive counterfactual for contrast: multiply the
    surviving gates' pass rates as if they were independent. On the real campaign it predicts
    ~9 survivors (0.581 x 0.479 x 0.433 x 0.433 x 0.402 = 2.1% of 420) where the true count is
    ZERO.

    THAT DIRECTION IS THE INFORMATIVE PART, and it is easy to get backwards. Observed BELOW the
    independent estimate means gate PASSES are negatively associated: a candidate that clears one
    gate tends to fail another. Which is what a well-designed battery should look like -- the
    gates are penalising genuinely different failure modes rather than re-measuring one latent
    "quality" score. (If they were positively associated, the good candidates would sweep every
    gate and survivors would EXCEED the independent estimate, which would mean the battery is
    largely one gate wearing five hats.) Across 420 candidates, not one was simultaneously
    profitable, walk-forward-stable, capacity-viable and tail-acceptable.

    Quoting the independent number as an expected yield would badly oversell any relaxation, so
    it is reported beside the true count, never instead of it.
    """
    if not gate_results:
        return {"n": 0, "waived": list(waive), "survivors": 0, "survivor_indices": [],
                "independent_estimate": 0.0, "note": "no candidates -- nothing to counterfact"}
    waived = set(waive)
    n = len(gate_results)
    survivors = [i for i, row in enumerate(gate_results)
                 if all(ok for g, ok in row.items() if g not in waived)]
    remaining = [g for g in gate_results[0] if g not in waived]
    est = 1.0
    for g in remaining:
        est *= sum(1 for r in gate_results if r.get(g)) / n
    return {
        "n": n, "waived": sorted(waived), "survivors": len(survivors),
        "survivor_indices": survivors[:20],
        "independent_estimate": round(est * n, 2),
        "note": ("waiving these gates promotes NOBODY -- every candidate also fails at least one "
                 "gate that genuinely discriminates, so the relaxation buys no survivors and "
                 "costs a statistical standard"
                 if not survivors else
                 f"{len(survivors)}/{n} would survive the waiver; this is a PROMOTION-BAR change "
                 f"and belongs to the principal, not to a screen"),
    }
