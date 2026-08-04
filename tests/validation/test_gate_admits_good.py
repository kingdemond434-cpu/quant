"""STANDING GATE-CI: can the real gauntlet still admit a genuine edge? (R0077)

WHY THIS TEST EXISTS. `scripts/certify_gauntlet.py` answers exactly this question against the real
420-candidate campaign -- and it is CRON-ONLY (ops/crontab.manifest, 10 5 * * *), takes >25 minutes,
and is gated by NOTHING in CI. Grepping tests/ for `certified_admits_good` or
`min_passing_true_sharpe` returned zero hits before this file: the desk could re-weld its own
promotion gate in a commit and no test anywhere would notice. Only the gate's REJECTIONS were ever
under test; its ability to ACCEPT was not.

That is the defect L1.43 names -- a gate that rejects ~100% carries zero information however
rigorous it looks -- and the desk has already paid for it once. The legacy path is measured WELDED:
`reports/gauntlet_certification.json` (2026-08-01) records it failing a true-Sharpe-15 control on
every seed, with `min_passing_true_sharpe: null` and White RC p pinned at the campaign constant
0.422 for every row, blocking 18 of 18 good candidates.

WHAT IS PINNED, AND WHAT IS DELIBERATELY NOT.
  * PINNED: the PER-CANDIDATE path admits a true-annual-Sharpe-5 control. 5.0 is the certification's
    own measured `min_passing_true_sharpe`, so this is a RATCHET on admitting power (L1.0) -- if a
    change pushes the bar above SR 5, the gate has re-welded and this test says so.
  * NOT PINNED: that a true-Sharpe-3 control passes. The certification measures SR-3 FAILING on both
    paths (Romano-Wolf adjusted p ~0.45 is the sole killer on the per-candidate path). Whether that
    bar is correctly calibrated is a live open question, but asserting SR-3 must pass would be
    demanding the bar be loosened to satisfy a test -- the exact failure this desk has paid for
    repeatedly. A test may pin what the gate DOES; it may not legislate what it SHOULD admit.
  * NOT PINNED: the legacy path. It is measured welded; asserting on it would freeze a known defect
    into the test suite as if it were the contract.

THE PAIRING IS NOT OPTIONAL. A test asserting only "a good candidate survives" is satisfied
perfectly by deleting every gate, so it would certify the most broken possible state as healthy.
The null control is what makes the positive assertion mean anything: together they say the gate
DISCRIMINATES, which is the only property worth defending. Never delete the null half to save time.

VERIFIED TO BITE, 2026-08-01, because a green test proves nothing until it has been made to fail.
Two welds were injected against this exact cohort and both were caught: `_DSR_THRESHOLD` raised
above the control's realised DSR -> blocked ['dsr']; `_PBO_THRESHOLD` driven to zero -> blocked
['pbo']. Worth recording the FIRST attempt too, since it is the trap: a weld at
`_DSR_THRESHOLD = 0.99999` did NOT fire, because the control's actual DSR is 0.999992 -- the
mutation was weaker than the signal, and read exactly like a rubber-stamp test until the metric
was printed. When checking whether a fence bites, size the mutation against the MEASURED value,
never against a round number that looks extreme.

Runtime ~80s (two real campaign_gate_stats bootstraps). That is the price of exercising the REAL
`validate()` rather than a stub -- and the desk's own record is that stubbed gate tests
(`tests/validation/test_positive_control.py` scores lambdas, not the gate) are what let the weld
survive unnoticed in the first place.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.autodiscovery.models import Family, Hypothesis, ValidationVerdict
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType
from libs.validation.positive_control import exact_sharpe_series, null_cohort

#: The certification's campaign shape. T=310 is the real matrix's observation count; N is reduced
#: from 420 to keep CI under ~80s. Fewer peers is the LOOSER direction for multiplicity, so a weld
#: that bites at N=40 certainly bites at N=420 -- this cannot produce a false alarm from N alone.
_T = 310
_N_PEERS = 40

#: The certification's measured `min_passing_true_sharpe` on the per-candidate path.
_ADMITTED_SHARPE = 5.0

_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="control", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="synthetic control",
    failure_modes=["synthetic control -- never tradeable"],
)


def _score_per_candidate(control: np.ndarray, peers: np.ndarray) -> ValidationVerdict:
    """Inject `control` as an extra campaign column and score it on the REAL per-candidate path."""
    m = np.column_stack([peers, control])
    gates = campaign_gate_stats(m)
    assert gates is not None, "campaign_gate_stats returned None on a >=2-column matrix"
    sh = np.append(
        np.array([sharpe_ratio(peers[:, i]) for i in range(peers.shape[1])]),
        sharpe_ratio(control),
    )
    return validate(
        control, campaign=gates, column=m.shape[1] - 1, hypothesis=_HYP,
        n_trials=max(400, m.shape[1]), sharpe_estimates=sh, returns_matrix=m,
    )


@pytest.fixture(scope="module")
def _cohort() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One fixed-seed cohort shared by both assertions, so they differ ONLY in the control."""
    rng = np.random.default_rng(7)
    peers = null_cohort(_N_PEERS, _T, rng=rng)
    good = exact_sharpe_series(_ADMITTED_SHARPE, _T, rng=rng)
    dud = null_cohort(1, _T, rng=rng)[:, 0]
    return peers, good, dud


class TestTheGateStillDiscriminates:
    def test_a_true_sharpe_5_edge_is_admitted(
            self, _cohort: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
        """THE ANTI-WELD ASSERTION. If this fails, the gauntlet rejects a genuine Sharpe-5 edge and
        the desk's promotion path admits nothing -- a silent, total loss of every future alpha."""
        peers, good, _ = _cohort
        res = _score_per_candidate(good, peers)
        blocking = [g for g, ok in res.gates.items() if not ok]
        assert res.survived, (
            f"the gate REJECTED a true-annual-Sharpe-{_ADMITTED_SHARPE} control, blocked by "
            f"{blocking}. The gauntlet has re-welded: reports/gauntlet_certification.json measured "
            f"this exact control PASSING the per-candidate path on every seed. Do NOT fix this by "
            f"loosening a threshold -- find what changed."
        )

    def test_a_zero_edge_control_is_rejected(
            self, _cohort: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
        """THE OTHER HALF. Without this, the assertion above is satisfied by deleting every gate."""
        peers, _, dud = _cohort
        res = _score_per_candidate(dud, peers)
        assert not res.survived, (
            "the gate ADMITTED a zero-edge null control -- it is no longer discriminating, and "
            "every 'survivor' it has produced since this broke is suspect."
        )
