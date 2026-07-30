"""Full institutional validation per candidate — every gate, no weakening, fail-closed.

Runs the complete stack and a candidate survives ONLY if every gate passes: economic mechanism,
CPCV (purged K-fold OOS consistency), PBO, Deflated Sharpe (trials-deflated), White's Reality Check,
Walk-Forward, capacity, fragility (tail risk), and an accelerated shadow check (final held-out
segment). Reuses the existing validation / discovery primitives. Thresholds are constants here and
never relaxed.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from libs.autodiscovery.models import Hypothesis, ValidationMetrics, ValidationVerdict
from libs.discovery.capacity import capacity_estimate
from libs.discovery.tail_risk import tail_risk
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, whites_reality_check
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus
from libs.validation.screen_select import ScreenSelection, screen_select
from libs.validation.stepwise import (
    CSCVResult,
    StepdownResult,
    cscv_candidate_pbo,
    romano_wolf_stepdown,
)

_PERIODS_PER_YEAR = 24 * 260
_DSR_THRESHOLD = 0.95
_PBO_THRESHOLD = 0.5       # same bar as PBOResult.overfit; only the ATTRIBUTION changed
# CAPACITY PARITY (principal order 2026-07-30; constitution L1.18/§42 made ARITHMETIC).
# The old bar was a FIXED $100,000 institutional floor. On a desk deploying ~$5k that rejects
# edges it could fill COMPLETELY -- measured 182 of 420 campaign candidates failed with capacity
# among their blockers (reports/gate_histogram.json: capacity 238/420 pass). An edge that can
# absorb 20x the desk's entire book was being called too small. That is capacity PICKINESS, and
# it costs exactly the compounding the desk exists to maximise: a $20k-capacity edge at $5k of
# equity is 100% usable and compounds identically to a $20m one until the quota binds.
# THE RULE: an edge fails capacity ONLY if it cannot absorb a meaningful slice of the desk's OWN
# size. It is then exploited to ITS OWN quota, never deprioritised for being small, and never
# ranked below a larger-capacity edge (L1.18: edges are edges).
# PRINCIPAL CLARIFICATION 2026-07-30: capital deploys from ~$1k and may start as low as ~$100.
# At $100 live, a $300-capacity edge is FULLY usable and must be exploited -- so the floor cannot
# be an institutional round number, it can only be the point where EXECUTION PHYSICS stops working
# (L1.5). Below ~20 venue-minimum notionals there is no room for a few economic round-trips, and
# that -- not a capital-size opinion -- is the only defensible absolute floor.
_DESK_EQUITY_FALLBACK_USD = 1.0e3     # used only when live equity is unreadable
# THE ADMISSION BAND IS A MINIMUM SLICE, NOT A MULTIPLE OF THE BOOK (principal 2026-07-30).
# A multiple was wrong and measurably so: at $1,000 equity a 2x rule marked capacity of $300,
# $800 and even $1,500 as OUTGROWN -- edges that can hold 30%, 80% and 150% of the whole book.
# The book runs MANY edges in parallel (that is the diversification the objective actually wants),
# so an edge never needs to hold the entire book; it needs to hold a slice big enough to matter.
# Consequence, which is the compounding point: the admissible band SLIDES UP with equity and stays
# INCLUSIVE at the small end forever -- at $1k everything from ~$200 up is in; at $50k a
# $300-capacity edge has finally become a rounding error and retires by OUTGROWTH.
_MIN_SLICE_FRACTION = 0.10            # an edge must hold >=10% of the book to be worth a quota
_CAPACITY_MULTIPLE_OF_EQUITY = 2.0    # RETAINED only for the gauntlet's own headroom bar
_VENUE_MIN_NOTIONAL_USD = 10.0        # Binance-class minimum order notional
_EXEC_VIABILITY_FLOOR_USD = 20.0 * _VENUE_MIN_NOTIONAL_USD   # ~$200: a handful of economic trips


def _desk_equity_usd() -> float:
    """Live deployable equity, read defensively. The capacity bar is RELATIVE to this so it
    scales with the desk instead of freezing an institutional assumption into a seed-stage book."""
    import json as _json
    from pathlib import Path as _Path
    for src, keys in ((_Path("web/cashcarry_live.json"), ("equity", "net_equity", "deployed")),
                      (_Path("data/cashcarry_config.json"), ("capital", "authorized_capital"))):
        try:
            d = _json.loads(src.read_text("utf-8"))
        except (OSError, _json.JSONDecodeError):
            continue
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
    return _DESK_EQUITY_FALLBACK_USD


def _min_capacity_usd() -> float:
    return max(_desk_equity_usd() * _CAPACITY_MULTIPLE_OF_EQUITY, _EXEC_VIABILITY_FLOOR_USD)


def capacity_status(capacity_usd: float, *, equity_usd: float | None = None) -> str:
    """ADMIT / OUTGROWN / SUB-VIABLE -- and the distinction is a lifecycle law, not bookkeeping.

    THE MODEL THE PRINCIPAL SPECIFIED (2026-07-30), and it is how small edges are supposed to end:
    a small-capacity edge is admitted and EXPLOITED TO ITS QUOTA while the book is small; as capital
    compounds past that quota the edge stops being able to hold a meaningful slice and retires by
    OUTGROWTH. That is natural attrition from SUCCESS, not failure --

      * OUTGROWN edges are NEVER graveyarded as dead mechanisms. Nothing was refuted: the mechanism
        was real, it was harvested to exhaustion, and the book simply grew past it. Graveyarding it
        would poison the novelty gate against a mechanism that WORKED, and would corrupt the
        family-level survival statistics that steer future search (L1.17).
      * SUB-VIABLE is the only genuine capacity rejection: the edge cannot support even a handful of
        economic round-trips at venue minimums, so execution physics (L1.5) kills it at ANY equity.
      * Small and large capacity are hunted SIMULTANEOUSLY and never ranked against each other
        (L1.18a). A pipeline that waits for big-capacity edges forfeits the compounding available
        right now, and compounding now is what buys the capital that makes big edges relevant.
    """
    eq = _desk_equity_usd() if equity_usd is None else float(equity_usd)
    if capacity_usd < _EXEC_VIABILITY_FLOOR_USD:
        return "SUB-VIABLE"
    if capacity_usd < eq * _MIN_SLICE_FRACTION:
        return "OUTGROWN"
    return "ADMIT"


def capacity_runway_days(capacity_usd: float, *, equity_usd: float | None = None,
                         growth_rate_annual: float = 1.0) -> float:
    """Days until the book grows past this edge's usable band -- its EXPIRY DATE.

    THE RACE THE PRINCIPAL NAMED (2026-07-30): a small-capacity edge is only worth anything if it
    reaches live BEFORE capital outgrows it. A validation pipeline slower than the runway delivers
    edges that are already rounding errors on arrival, which is not caution -- it is a guaranteed
    zero. So runway is computed and COMPARED to pipeline latency (see `capacity_race`), and the
    forward-slot queue is ordered by EXPIRY, shortest first, because a long-runway edge loses
    nothing by waiting and a short-runway one loses everything.

    growth_rate_annual: continuous growth of equity, 1.0 = 100%/yr. The desk's own target band is
    80-120%/yr (GROWTH_UNLOCK_LADDER), so the default is deliberately the middle of the mandate
    rather than an optimistic number.
    """
    import math
    eq = _desk_equity_usd() if equity_usd is None else float(equity_usd)
    if eq <= 0 or growth_rate_annual <= 0:
        return float("inf")
    # equity at which this edge becomes a rounding error on the book
    outgrow_at = capacity_usd / _MIN_SLICE_FRACTION
    if outgrow_at <= eq:
        return 0.0                                      # already outgrown
    return 365.0 * math.log(outgrow_at / eq) / growth_rate_annual


def capacity_race(capacity_usd: float, *, validation_days: float,
                  equity_usd: float | None = None,
                  growth_rate_annual: float = 1.0) -> dict[str, Any]:
    """Does this edge reach live before the book outgrows it? Verdict + the honest remedy.

    Verdicts:
      REACHES-LIVE   runway exceeds the pipeline latency with margin -- ship it normally.
      TIGHT          it lands with little life left; worth prioritising in the slot queue.
      DOA            it is outgrown before validation could finish. THE REMEDY IS NEVER A SHORTER
                     CLOCK OR A LOWER BAR (L1.6 -- the confirmation bar never loosens). The only
                     honest accelerants are MORE OBSERVATIONS PER DAY (the desk measured this: an
                     8h funding panel carries ~sqrt(3)x the evidence rate of a daily one at
                     vif 1.008, gap #44) and NOT QUEUEING -- run the slot now rather than later.
                     If neither is available the edge is structurally unreachable at this equity
                     and is recorded as such, not silently shelved.
    """
    runway = capacity_runway_days(capacity_usd, equity_usd=equity_usd,
                                  growth_rate_annual=growth_rate_annual)
    if runway <= validation_days:
        verdict = "DOA"
    elif runway < validation_days * 2.0:
        verdict = "TIGHT"
    else:
        verdict = "REACHES-LIVE"
    return {"capacity_usd": capacity_usd, "runway_days": round(runway, 1),
            "validation_days": validation_days, "verdict": verdict,
            "slot_priority": round(runway, 1),      # ascending: shortest runway is served first
            "remedy": ("higher-frequency evidence (8h panel ~sqrt(3)x rate) and/or an immediate "
                       "slot -- never a shorter clock or a lower bar"
                       if verdict != "REACHES-LIVE" else "none needed")}
_CPCV_MIN_POSITIVE = 0.6   # >=60% of purged folds positive


def _cpcv_positive_fraction(returns: np.ndarray, *, k: int = 5) -> float:
    folds = np.array_split(returns, k)
    positive = [f.mean() > 0 for f in folds if len(f) > 1]
    return float(np.mean(positive)) if positive else 0.0


def campaign_pbo_rc(
    returns_matrix: np.ndarray,
) -> tuple[PBOResult | None, RealityCheckResult | None]:
    """Compute PBO and White's Reality Check ONCE per campaign (they depend only on the matrix).

    DEPRECATED as a GATE input -- kept for diagnostics and for call sites not yet migrated.

    Both statistics take only the matrix; the candidate's own returns are never an input.  Used as
    per-candidate gates they are therefore campaign CONSTANTS, and the "no change to the verdict"
    that made caching them look free is exactly the defect: every candidate in a batch gets the
    same verdict whatever its merit.  Measured 2026-07-29 on the real 420-candidate campaign --
    PBO 0.6159 (>0.5) and White RC p 0.4220 (>=0.05) -- which alone forced 420/420 rejections.
    Measured on a synthetic campaign containing one strong winner, the same two gates pass EVERY
    pure-noise candidate.  Too strict and too loose, decided by the batch rather than the
    candidate.

    Use :func:`campaign_gate_stats` + ``validate(campaign=..., column=...)`` instead.
    """
    if returns_matrix.shape[1] < 2:
        return None, None
    return probability_backtest_overfitting(returns_matrix), whites_reality_check(returns_matrix)


class CampaignGates:
    """Per-candidate multiplicity statistics for one campaign, computed once.

    Holds the candidate-aware replacements (CSCV rank-consistency, Romano-Wolf stepdown) and the
    legacy campaign statistics, which stay available as diagnostics of the SEARCH PROCEDURE --
    which is the thing they actually measure.
    """

    __slots__ = ("cscv", "legacy_pbo", "legacy_rc", "screen", "stepdown")

    def __init__(
        self,
        cscv: CSCVResult,
        stepdown: StepdownResult,
        legacy_pbo: PBOResult | None,
        legacy_rc: RealityCheckResult | None,
    ) -> None:
        self.cscv = cscv
        self.stepdown = stepdown
        self.legacy_pbo = legacy_pbo
        self.legacy_rc = legacy_rc
        # SCREEN-STAGE SELECTION (gap #71, 2026-07-30). Computed and REPORTED alongside the
        # family-wise verdict; it does NOT change the survival gate here. The measured reason:
        # Romano-Wolf FWER admits 0/420 at every window tested (best adjusted p 0.522 at min-length,
        # 0.089 at max-observation), so as a SCREEN gate it carries zero information about candidate
        # quality -- and a bar that rises with generation volume is what TWO_STAGE_DISCOVERY_LAW
        # forbids. Promotion authority is untouched: forward clocks keep Holm/FWER on <=12 slots.
        self.screen: ScreenSelection | None = None
        with_screen = screen_select(stepdown, q=0.05, method="by") if stepdown else None
        self.screen = with_screen


def campaign_gate_stats(returns_matrix: np.ndarray) -> CampaignGates | None:
    """One pass over the campaign matrix yielding PER-CANDIDATE pbo / significance verdicts.

    Same thresholds as before (PBO <= 0.5, significance at 5%) -- only the *attribution* changes,
    from one campaign verdict imposed on everyone to a verdict each candidate earns.  Romano-Wolf
    still controls family-wise error across all N, so multiplicity is paid for in full.
    """
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        return None
    legacy_pbo, legacy_rc = campaign_pbo_rc(matrix)
    return CampaignGates(
        cscv=cscv_candidate_pbo(matrix),
        stepdown=romano_wolf_stepdown(matrix),
        legacy_pbo=legacy_pbo,
        legacy_rc=legacy_rc,
    )


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
    campaign: CampaignGates | None = None,
    column: int | None = None,
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
    # Overfitting / significance. PREFERRED path: per-candidate statistics from `campaign`, which
    # this candidate earns on its own column. LEGACY path (no campaign supplied): the campaign
    # constants, retained only so unmigrated call sites keep their exact prior behaviour.
    has_peers = returns_matrix.shape[1] >= 2
    per_candidate = campaign is not None and column is not None
    if per_candidate:
        assert campaign is not None and column is not None  # narrowed by per_candidate
        cand_pbo = campaign.cscv.candidate_pbo[column]
        pbo_ok = cand_pbo <= _PBO_THRESHOLD
        sig_ok = campaign.stepdown.rejected[column]
        pbo_value, reality_value = cand_pbo, campaign.stepdown.adjusted_p[column]
    else:
        if pbo is None and has_peers:
            pbo = probability_backtest_overfitting(returns_matrix)
        if rc is None and has_peers:
            rc = whites_reality_check(returns_matrix)
        pbo_ok = pbo is not None and not pbo.overfit
        sig_ok = rc is not None and rc.significant_at_5pct
        pbo_value = pbo.pbo if pbo is not None else 1.0
        reality_value = rc.p_value if rc is not None else 1.0
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
        pbo=pbo_value,
        reality_p=reality_value,
        capacity_usd=cap.capacity_usd,
        fragility=tail.tail_risk_score,
    )

    gates = {
        "economic_mechanism": bool(hypothesis.failure_modes),   # declared before testing
        "expected_value": metrics.expected_value > 0,
        "cpcv": _cpcv_positive_fraction(arr) >= _CPCV_MIN_POSITIVE,
        "walk_forward": wf.status is WalkForwardStatus.PASSED,
        "dsr": dsr.passed,
        "pbo": pbo_ok,
        "reality_check": sig_ok,
        # capacity parity: relative to the desk's OWN size (see _min_capacity_usd), never a
        # fixed institutional floor. Small edges are admitted and exploited to their own quota.
        "capacity": cap.capacity_usd >= _min_capacity_usd(),
        "fragility": tail.acceptable,
    }
    failed = [name for name, ok in gates.items() if not ok]
    return ValidationVerdict(
        survived=not failed, gates=gates,
        rejection_reason="" if not failed else "failed: " + ", ".join(failed),
        metrics=metrics,
    )
