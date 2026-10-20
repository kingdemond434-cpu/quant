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
    """THE FINDING, re-read under the fixed bar (principal 2026-10-13: "make sure the bars never
    raise never ever penalty never inflation due to trials"). The hurdle at the campaign's shape
    is the SAME whether the campaign tested 5, 421 or 10,000 candidates -- the bar's N is
    trial_count_guard.BAR_N -- and the candidate count is still REPORTED beside it.

    What remains true is that the WINDOW decides: at T=310 a genuine SR-2 strategy clears the
    fixed bar well under half the time, so a 0-of-N record on that window still says little
    about the price space."""
    from libs.research.trial_count_guard import BAR_N
    d = design_power(_N + 1, _T)
    assert d["n_trials"] == _N + 1                       # the count is reported...
    assert d["bar_n"] == BAR_N                           # ...and the bar charges the fixed N
    for n in (5, 30, _N + 1, 10_000):
        assert design_power(n, _T)["hurdle_annual_sharpe"] == d["hurdle_annual_sharpe"]
    # below BAR_N the charge is the count itself (min form): never above the fixed bar
    for n in (1, 2, 4):
        assert design_power(n, _T)["hurdle_annual_sharpe"] <= d["hurdle_annual_sharpe"]
    assert d["power_by_true_annual_sharpe"]["2"] < 0.5
    assert d["underpowered_below_annual_sharpe"] >= 2.0


def test_shape_moves_the_hurdle_and_nothing_is_relaxed_to_do_it():
    """The only legitimate response to an unpassable gate is a longer window; every threshold
    stays where it is. Narrowing the campaign no longer moves the hurdle at all, because a wider
    one never raised it (fixed bar N, principal 2026-10-13)."""
    wide_short = dsr_hurdle_annual(_N, _T)
    narrow_long = dsr_hurdle_annual(30, 1250)
    assert narrow_long < wide_short / 2.0
    assert dsr_hurdle_annual(30, _T) == wide_short         # the count buys and costs nothing
    assert dsr_hurdle_annual(_N, 1250) < wide_short        # lengthening alone helps
    assert dsr_hurdle_annual(_N, 1250) == narrow_long


def test_the_design_table_does_not_inherit_the_certifiers_trial_floor():
    """REGRESSION PIN. The table passes each N directly (no _FAMILY_TRIAL_BUDGET floor) and,
    under the fixed bar, every N in a row prices the IDENTICAL hurdle: a trial count neither
    raises nor lowers the bar. A row that stops being flat means a count got back into the bar."""
    table = design_power(_N + 1, _T)["alternative_shapes"]
    for row in table.values():
        vals = list(row.values())
        assert len(vals) == 5 and all(v == vals[0] for v in vals), row
    t310, t1250 = table["T=310"]["N=420"], table["T=1250"]["N=420"]
    assert t1250 < t310                                   # the window still moves it


def test_the_hurdle_tracks_the_gate_rather_than_restating_it():
    """If the hurdle were a hardcoded literal it would drift away from the gate the first time
    anything upstream changed. It is derived from expected_max_sharpe at the fixed bar N and
    _DSR_THRESHOLD, so it moves with T and with them -- and never with the trial count."""
    from libs.autodiscovery.validation import _DSR_THRESHOLD
    assert design_power(_N + 1, _T)["dsr_threshold"] == _DSR_THRESHOLD
    assert dsr_hurdle_annual(_N, _T) > dsr_hurdle_annual(_N, _T * 2)
    assert dsr_hurdle_annual(_N, _T) == dsr_hurdle_annual(_N // 4, _T)


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
    # TRIAL-COUNT GUARD (2026-10-14): BH/BY charge m at min(m, BAR_N), so the rank-1 boundary is
    # q/min(m, 5) -- still Bonferroni EXACTLY, at the pinned N. The point of this test stands: at
    # rank 1 FDR is no looser than the FWER bar; the count (420) no longer sets either.
    from libs.research.trial_count_guard import BAR_N
    m_bar = min(m, BAR_N)
    hm = float(sum(1.0 / i for i in range(1, m + 1)))
    # a lone candidate just inside the pinned Bonferroni boundary, the rest pure noise
    p = np.concatenate([[q / m_bar * 0.99], np.linspace(0.2, 1.0, m - 1)])
    assert benjamini_hochberg(p, alpha=q).rejected[0] is True
    # ...and just outside it, BH rejects nothing -- identical to Bonferroni, not looser
    p_out = np.concatenate([[q / m_bar * 1.01], np.linspace(0.2, 1.0, m - 1)])
    assert benjamini_hochberg(p_out, alpha=q).n_rejected == 0
    # BY (what screen_select is wired with, method="by"): each rank is charged min(its own
    # charge m*H_m/i, BAR_N) (re-audit of 6de7b1a99), so at rank 1 BY is Bonferroni at BAR_N
    # exactly too -- never looser, and the harmonic factor (H_m ~ 6.6 at m=420) no longer
    # stacks a count-driven penalty on top of the fixed bar.
    assert q / (m * hm) < q / m_bar
    assert benjamini_yekutieli(p, alpha=q).rejected[0] is True
    assert benjamini_yekutieli(p_out, alpha=q).n_rejected == 0


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
    verdict = validate(m[:, 0], hypothesis=hyp, periods_per_year=365.0, n_trials=5,
                       sharpe_estimates=sh, returns_matrix=m)
    assert not [g for g in verdict.gates if "screen" in g], (
        f"the BY-FDR screen has become a survival gate: {sorted(verdict.gates)}")
    # ...and the FWER stepdown IS the one that decides, on the per-candidate path.
    assert "campaign.stepdown.rejected[column]" in inspect.getsource(validate)
