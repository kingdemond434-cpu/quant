"""Is the gauntlet too harsh -- and would the desk's OWN diagnosed fix have helped?

Both halves are measured here rather than argued, because both were previously answered by
assertion. The certification proved the gate ADMITS a true edge (SR_true=10 passes) and REJECTS
noise (SR_true=0 fails five gates). It could not say how big an edge must be, and that is the
number that decides whether "0 survivors from 420" is a fact about crypto or a fact about the
campaign's resolution.
"""
from __future__ import annotations

import numpy as np
from scripts.certify_gauntlet import design_power, dsr_hurdle_annual

from libs.validation.fdr import benjamini_hochberg, benjamini_yekutieli

# The campaign the 0-of-420 record was measured on.
_N, _T = 420, 310


def test_the_campaign_shape_cannot_resolve_a_world_class_edge():
    """THE FINDING. A world-class systematic book runs a true annualised Sharpe of 2-3. At the
    campaign's own shape the gate demands ~5 just to reach dsr>=0.95, so a genuine SR-2 strategy
    clears it well under 1% of the time.

    The consequence is the whole point: 0-of-420 is EXACTLY what an underpowered campaign returns
    whether or not the 420 contained real edges, so the null result carries no information about
    the price space and must not be read as 'crypto is picked clean'."""
    d = design_power(_N + 1, _T)
    assert d["hurdle_annual_sharpe"] > 4.5
    assert d["power_by_true_annual_sharpe"]["2"] < 0.05
    assert d["power_by_true_annual_sharpe"]["3"] < 0.10
    assert d["underpowered_below_annual_sharpe"] >= 4.0


def test_shape_moves_the_hurdle_and_nothing_is_relaxed_to_do_it():
    """The only legitimate response to an unpassable gate. Fewer, mechanism-motivated candidates
    over longer history buy resolution while every threshold stays where it is -- lowering the
    0.95 tolerance instead would manufacture survivors."""
    wide_short = dsr_hurdle_annual(_N, _T)
    narrow_long = dsr_hurdle_annual(30, 1250)
    assert narrow_long < wide_short / 2.0
    # both knobs pull independently, so neither alone is the answer
    assert dsr_hurdle_annual(30, _T) < wide_short          # narrowing alone helps
    assert dsr_hurdle_annual(_N, 1250) < wide_short        # lengthening alone helps


def test_the_design_table_does_not_inherit_the_certifiers_trial_floor():
    """REGRESSION PIN, on a defect this file's first draft shipped. The table applied
    certify_gauntlet's own _FAMILY_TRIAL_BUDGET=120 to every cell, collapsing N=100/30/10/5 to a
    single identical number -- which reads as 'narrowing a campaign below 120 buys nothing' and
    would have argued the desk out of its only working lever. Production callers pass the real
    candidate count with no floor (run_discovery n_trials=len(lib), run_crypto_portfolio
    matrix.shape[1]), so the design question must use N directly."""
    t = design_power(_N + 1, _T)["alternative_shapes"]["T=310"]
    assert t["N=5"] < t["N=10"] < t["N=30"] < t["N=100"] < t["N=420"]


def test_the_hurdle_tracks_the_gate_rather_than_restating_it():
    """If the hurdle were a hardcoded 5.04 it would drift away from the gate the first time
    anything upstream changed, and the table would confidently describe a gate that no longer
    exists. It is derived from expected_max_sharpe and _DSR_THRESHOLD, so it moves with them."""
    from libs.autodiscovery.validation import _DSR_THRESHOLD
    assert design_power(_N + 1, _T)["dsr_threshold"] == _DSR_THRESHOLD
    # monotone in both arguments, which a constant could not be
    assert dsr_hurdle_annual(_N, _T) > dsr_hurdle_annual(_N, _T * 2)
    assert dsr_hurdle_annual(_N, _T) > dsr_hurdle_annual(_N // 4, _T)


# ---- gap #71's premise, corrected ---------------------------------------------------------------

def test_fdr_buys_no_power_for_the_best_candidate():
    """THE CORRECTION. gap #71 diagnosed the screen's Romano-Wolf FWER as a bar that rises with
    generation volume -- true, and forbidden by TWO_STAGE_DISCOVERY_LAW -- and built
    screen_select() to replace it with Benjamini-Hochberg/Yekutieli.

    But a campaign asking 'did ANYTHING survive' is asking about its single best candidate, and at
    rank 1 the BH threshold is q/m, which is Bonferroni EXACTLY. FDR is more powerful only when
    many candidates are individually significant; it cannot rescue a lone edge. BY is worse still,
    stricter by the harmonic factor H_m ~= 6.6 at m=420.

    So switching the screen to FDR would not have lowered the detection floor -- which is why the
    real constraint is the campaign's shape, measured above, and not the multiplicity method."""
    m, q = 420, 0.05
    hm = float(sum(1.0 / i for i in range(1, m + 1)))
    # a lone candidate just inside the Bonferroni boundary, the rest pure noise
    p = np.concatenate([[q / m * 0.99], np.linspace(0.2, 1.0, m - 1)])
    assert benjamini_hochberg(p, alpha=q).rejected[0] is True
    # ...and just outside it, BH rejects nothing -- identical to Bonferroni, not looser
    p_out = np.concatenate([[q / m * 1.01], np.linspace(0.2, 1.0, m - 1)])
    assert benjamini_hochberg(p_out, alpha=q).n_rejected == 0
    # BY, which is what screen_select is actually wired with (method="by"), is STRICTER
    assert benjamini_yekutieli(p, alpha=q).n_rejected == 0
    assert q / (m * hm) < q / m


def test_the_screen_selection_is_computed_but_does_not_gate():
    """Stated so the wiring is a decision on the record rather than an oversight someone later
    'fixes' without pricing it. validate() reads stepdown.rejected (FWER); CampaignGates.screen is
    carried alongside as a diagnostic. Given the test above -- FDR buys no power at rank 1 -- the
    unwired state costs nothing today, and rewiring it would shortlist false names without
    lowering the floor.

    ASSERTED ON THE GATE KEYS, NOT ON THE SOURCE TEXT. The original form of this test grepped the
    body of validate() for the substring "screen" after `gates = {`, which made it fail the moment
    an unrelated COMMENT used the word (it did, on 2026-08-01, in a note explaining that the
    gauntlet is a screen with zero promotion authority). A test that a prose edit can break is a
    test someone eventually deletes instead of reading, and it was checking a proxy anyway: what
    matters is whether the screen selection appears among the gates that decide survival, and
    that is directly observable from the verdict.
    """
    import inspect

    import numpy as np

    from libs.autodiscovery.models import Family, Hypothesis
    from libs.autodiscovery.validation import validate
    from libs.validation.economic_prior import MechanismType

    rng = np.random.default_rng(0)
    m = rng.normal(0.0004, 0.01, (600, 5))
    hyp = Hypothesis(family=Family.LIQUIDITY, subtype="s", symbol="X", params={},
                     mechanism=MechanismType.LIQUIDITY, edge_source="fixture",
                     failure_modes=["decays"])
    sh = np.array([m[:, i].mean() / m[:, i].std() for i in range(m.shape[1])])
    verdict = validate(m[:, 0], hypothesis=hyp, n_trials=5, sharpe_estimates=sh,
                       returns_matrix=m)
    assert not [g for g in verdict.gates if "screen" in g], (
        f"the BY-FDR screen has become a survival gate: {sorted(verdict.gates)}")
    # ...and the FWER stepdown IS the one that decides, on the per-candidate path.
    assert "campaign.stepdown.rejected[column]" in inspect.getsource(validate)
