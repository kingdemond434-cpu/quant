"""The invariants that make slot admission safe rather than a relaxation.

The three that matter are test_admissions_never_exceed_idle_slots (exceeding the cap invalidates
the Holm correction, which is the ONE way this module could make the desk less safe),
test_a_structural_block_cannot_be_out_ranked, and test_admission_never_returns_a_position_size.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.slot_registry import MAX_FORWARD_SLOTS
from libs.validation.screen_admission import (
    MIN_ADMISSION_OOS_SHARPE,
    STATISTICAL_GATES,
    STRUCTURAL_GATES,
    admit,
    break_even_win_rate,
    rank_score,
)


def _cand(name: str, *, oos: float = 0.8, fail_struct: tuple[str, ...] = (),
          fail_stat: tuple[str, ...] = ()) -> dict:
    gates = {g: g not in fail_struct for g in STRUCTURAL_GATES}
    gates.update({g: g not in fail_stat for g in STATISTICAL_GATES})
    return {"name": name, "gates": gates, "oos_sharpe": oos, "dsr": 0.9, "reality_p": 0.02}


# ------------------------------------------------------------------ break-even win rate

def test_break_even_win_rate_matches_the_measured_example():
    """avg win 5.72%, avg loss 3.13% -> p* = 35.4%, realised 41.3%. That 5.9-point gap compounded
    over 758 trades WAS the 24.9x return; nothing else in the result mattered."""
    assert break_even_win_rate(5.72, 3.13) == pytest.approx(0.354, abs=0.001)


def test_symmetric_payoffs_break_even_at_a_coin_flip():
    assert break_even_win_rate(1.0, 1.0) == pytest.approx(0.5)


def test_a_bigger_average_win_lowers_the_bar():
    assert break_even_win_rate(6.0, 3.0) < break_even_win_rate(3.0, 3.0)


def test_no_average_winner_can_never_break_even():
    """Returning 0.5 here would read as an easy bar for a strategy that cannot make money at any
    win rate."""
    assert break_even_win_rate(0.0, 2.0) == 1.0
    assert break_even_win_rate(-1.0, 2.0) == 1.0


def test_it_is_a_structural_gate_not_a_statistical_one():
    """Per-trade arithmetic, not a p-value. Forward data does not repair a strategy whose average
    winner is smaller than its average loser by more than its win rate covers."""
    assert "break_even_win_rate" in STRUCTURAL_GATES
    assert "break_even_win_rate" not in STATISTICAL_GATES


# --------------------------------------------------------------------- the safety invariants

@pytest.mark.parametrize("idle", [0, 1, 5, 12])
def test_admissions_never_exceed_idle_slots(idle: int):
    """THE load-bearing invariant. Holm is priced at exactly MAX_FORWARD_SLOTS concurrent tests;
    admitting more invalidates the correction, and that is the single way this module could make
    the desk genuinely less safe rather than more productive."""
    plan = admit([_cand(f"c{i}", oos=0.5 + float(i) / 10) for i in range(40)], idle_slots=idle)
    assert len(plan.admitted) <= idle
    assert plan.idle_slots_after == idle - len(plan.admitted)


def test_never_admits_beyond_the_registry_cap():
    plan = admit([_cand(f"c{i}") for i in range(100)], idle_slots=MAX_FORWARD_SLOTS)
    assert len(plan.admitted) <= MAX_FORWARD_SLOTS


def test_a_structural_block_cannot_be_out_ranked():
    """A spectacular OOS Sharpe must not buy past a missing economic mechanism. If rank could
    override structure, this module would be a promotion gate rather than an ordering."""
    cands = [_cand("no_mechanism", oos=99.0, fail_struct=("economic_mechanism",)),
             _cand("modest_but_sound", oos=0.4)]
    plan = admit(cands, idle_slots=5)
    assert [a.name for a in plan.admitted] == ["modest_but_sound"]
    assert [b.name for b in plan.blocked] == ["no_mechanism"]


@pytest.mark.parametrize("gate", STRUCTURAL_GATES)
def test_every_structural_gate_actually_blocks(gate: str):
    plan = admit([_cand("x", oos=50.0, fail_struct=(gate,))], idle_slots=12)
    assert not plan.admitted
    assert plan.blocked[0].blocked_by == (gate,)


@pytest.mark.parametrize("gate", STATISTICAL_GATES)
def test_a_statistical_failure_ranks_but_does_not_block(gate: str):
    """The whole point. The forward stage tests 'distinguishable from noise' on unseen data with
    the multiplicity already priced, so a backtest p-value orders candidates rather than killing
    them."""
    plan = admit([_cand("x", fail_stat=(gate,))], idle_slots=1)
    assert [a.name for a in plan.admitted] == ["x"]
    assert plan.admitted[0].statistical_failures == (gate,)


def test_admission_never_returns_a_position_size():
    """Admission confers a forward CLOCK. Anything resembling a size, weight or notional in this
    output would mean the screen had quietly acquired promotion authority."""
    plan = admit([_cand("x")], idle_slots=1)
    banned = ("size", "notional", "weight", "capital", "allocation", "usd", "qty")
    for a in plan.admitted:
        for f in vars(a):
            assert not any(b in f.lower() for b in banned), f"{f} looks like a sizing field"
    assert "never capital" in " ".join(plan.notes)


# ------------------------------------------------------------------------------- ordering

def test_higher_oos_sharpe_ranks_first():
    plan = admit([_cand("low", oos=0.2), _cand("high", oos=1.4), _cand("mid", oos=0.7)],
                 idle_slots=2)
    assert [a.name for a in plan.admitted] == ["high", "mid"]


def test_clearing_more_statistical_gates_breaks_a_tie_but_cannot_flip_a_real_gap():
    tie_gates = dict.fromkeys(STRUCTURAL_GATES + STATISTICAL_GATES, True)
    fewer = dict(tie_gates, dsr=False, pbo=False)
    assert rank_score(tie_gates, oos_sharpe=1.0, dsr=0.9, reality_p=0.01) > \
        rank_score(fewer, oos_sharpe=1.0, dsr=0.9, reality_p=0.01)
    # ...but a 0.5 OOS gap must dominate any number of cleared gates.
    assert rank_score(fewer, oos_sharpe=1.5, dsr=0.9, reality_p=0.01) > \
        rank_score(tie_gates, oos_sharpe=1.0, dsr=0.9, reality_p=0.01)


def test_ranking_is_deterministic_under_ties():
    a = admit([_cand("b"), _cand("a"), _cand("c")], idle_slots=2)
    b = admit([_cand("c"), _cand("a"), _cand("b")], idle_slots=2)
    assert [x.name for x in a.admitted] == [x.name for x in b.admitted]


# ------------------------------------------------------------------------ honest reporting

def test_an_all_structural_wipeout_is_reported_as_a_real_result():
    """If every candidate fails a structural gate, the answer is that the mechanisms have no
    edge -- and widening the screen does not fix it. The notes must say so rather than implying
    the gate was the problem."""
    plan = admit([_cand(f"c{i}", fail_struct=("expected_value",)) for i in range(5)],
                 idle_slots=12)
    assert not plan.admitted
    assert any("STRUCTURAL" in n for n in plan.notes)


def test_a_saturated_forward_stage_admits_nothing_and_says_why():
    plan = admit([_cand("x")], idle_slots=0)
    assert not plan.admitted
    assert any("saturated" in n for n in plan.notes)


def test_empty_input_is_handled_without_inventing_an_admission():
    plan = admit([], idle_slots=12)
    assert not plan.admitted and not plan.blocked and not plan.ranked_out


def test_a_candidate_missing_a_gate_key_is_not_silently_blocked():
    """Absent != failed. A caller that does not compute a gate must not have its candidate killed
    by the omission -- that is the `beats_baselines` defect in the opposite direction."""
    plan = admit([{"name": "sparse", "gates": {"economic_mechanism": True},
                   "oos_sharpe": 1.0, "dsr": 0.9, "reality_p": 0.01}], idle_slots=1)
    assert [a.name for a in plan.admitted] == ["sparse"]


def test_every_ranked_out_candidate_would_have_been_admitted_with_more_slots():
    # All comfortably above the relevance floor, so scarcity is the ONLY thing separating them.
    cands = [_cand(f"c{i}", oos=0.5 + float(i) / 10) for i in range(6)]
    tight, loose = admit(cands, idle_slots=2), admit(cands, idle_slots=6)
    admitted_loose = {a.name for a in loose.admitted}
    for r in tight.ranked_out:
        assert r.name in admitted_loose, "ranked-out must mean scarcity, never a hidden block"
    assert np.isclose(len(loose.admitted), 6)


# ------------------------------------------------------------------- the relevance floor

def test_a_near_zero_oos_candidate_never_occupies_a_slot():
    """The failure that appeared the moment the statistical wall came down: replaying the real
    campaign filled all twelve slots with near-zero OOS Sharpe. A forward clock runs for months,
    so a slot spent on noise BLOCKS a real edge for that whole period. An idle slot costs nothing.

    RESTATED IN ANNUALISED UNITS. This test originally used oos=0.02 and called it "~zero". It is
    not: validate() reports PER-BAR Sharpe, so 0.02 is 0.38 ANNUALISED -- nearly the bottom of the
    0.5-1.5 real-edge band. The test passed only because the floor carried the same 19x units
    error, and the two errors cancelled. The intent was always "annualised noise gets no slot", so
    that is what it now says."""
    noise = 0.05 / (PPY_DAILY ** 0.5)          # 0.05 ANNUALISED -- genuinely nothing
    plan = admit([_cand(f"noise{i}", oos=noise) for i in range(20)], idle_slots=12)
    assert not plan.admitted
    assert plan.idle_slots_after == 12
    assert any("relevance floor" in n for n in plan.notes)


def test_the_floor_sits_below_the_real_edge_band_so_noisy_measurement_is_not_fatal():
    """A true 1.0 edge measured on a short window can print well under 0.5. The floor must sit
    BELOW the band's lower edge or it rejects real edges for being imprecisely measured.

    COMPARED IN ANNUALISED UNITS, which is the bug this test failed to catch the first time: it
    compared the PER-BAR floor against the ANNUALISED band, so 0.25 per-bar (4.78 annualised)
    sailed through a check that was supposed to stop exactly that."""
    from libs.validation.robustness_filters import REAL_EDGE_OOS_SHARPE_BAND
    assert 0.0 < MIN_ADMISSION_ANN_SHARPE < REAL_EDGE_OOS_SHARPE_BAND[0]


def test_the_relevance_floor_cannot_be_out_ranked_either():
    flat = 0.05 / (PPY_DAILY ** 0.5)           # 0.05 ANNUALISED, not 0.1 per-bar (= 1.9 ann)
    plan = admit([_cand("clears_everything_but_flat", oos=flat)], idle_slots=12)
    assert not plan.admitted
    assert "below_relevance_floor" in plan.blocked[0].blocked_by


def test_the_real_campaign_correctly_admits_nothing():
    """129 textbook mechanisms, max OOS Sharpe 0.100. Under admission that campaign still fills
    zero slots -- which is the honest answer for mechanisms already measured as picked clean, and
    the proof that this module did not simply lower the bar."""
    import json
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[2] / "reports/transcript_candidate_run.json"
    if not p.exists():
        pytest.skip("campaign artifact absent (reports/ is gitignored)")
    rows = json.loads(p.read_text("utf-8"))
    plan = admit([{"name": r.get("name", "?"), "gates": r.get("gates") or {},
                   "oos_sharpe": r.get("oos_sharpe", 0.0), "dsr": r.get("dsr", 0.0),
                   "reality_p": r.get("reality_p", 1.0)} for r in rows], idle_slots=12)
    assert not plan.admitted, f"admitted {[a.name for a in plan.admitted]} from a 0-survivor run"


def test_a_missing_oos_field_fails_the_floor_rather_than_passing_it():
    """Unknown must block here: this is the promotion-adjacent direction, not the discovery
    pre-filter, and a candidate whose OOS nobody computed has not earned a scarce clock."""
    plan = admit([{"name": "no_oos", "gates": {}}], idle_slots=12)
    assert not plan.admitted


# --------------------------------------------------- turnover: priced ONCE, never twice

def test_a_net_sharpe_is_not_penalised_for_turnover_again():
    """The double-correction trap, and it is the exact defect that made this gauntlet 4x too
    strict: DSR deflated trials the campaign layer had already deflated. positions_to_returns
    charges 6 bps per turn, so a Sharpe built through it already carries its costs -- subtracting
    turnover from that number a second time would repeat the mistake in a new place."""
    g = dict.fromkeys(STRUCTURAL_GATES + STATISTICAL_GATES, True)
    with_turn = rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01,
                           turnover=0.60, cost_basis="net")
    without = rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01, cost_basis="net")
    assert with_turn == pytest.approx(without)


def test_a_gross_sharpe_is_penalised_for_turnover():
    g = dict.fromkeys(STRUCTURAL_GATES + STATISTICAL_GATES, True)
    hi = rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01,
                    turnover=0.60, cost_basis="gross")
    lo = rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01,
                    turnover=0.15, cost_basis="gross")
    assert lo > hi, "at equal gross Sharpe the 15%-turnover alpha must outrank the 60% one"


def test_an_undeclared_cost_basis_is_treated_as_gross_and_reported():
    """Unknown must not read as 'costs already charged'. That branch admits a candidate whose
    entire edge is fees -- and this desk measured realised cost at 7.75x its own prediction, so
    even a declared NET is optimistic."""
    g = dict.fromkeys(STRUCTURAL_GATES + STATISTICAL_GATES, True)
    assert rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01, turnover=0.5) < \
        rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01, turnover=0.5, cost_basis="net")
    plan = admit([_cand("x")], idle_slots=1)
    assert any("UNMEASURED cost basis" in n for n in plan.notes)


def test_declaring_net_removes_the_unmeasured_warning():
    plan = admit([_cand("x")], idle_slots=1, cost_basis="net")
    assert not any("UNMEASURED cost basis" in n for n in plan.notes)


def test_a_missing_turnover_field_is_not_penalised_as_zero_or_infinite():
    """Absent turnover means nobody measured it; it must neither be treated as free (0.0, which
    flatters) nor as maximal (which would kill every candidate silently)."""
    g = dict.fromkeys(STRUCTURAL_GATES + STATISTICAL_GATES, True)
    assert rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01, turnover=None) == \
        pytest.approx(rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01,
                                 turnover=None, cost_basis="net"))


# ================================================================= units and sample adequacy
# Added after the floor shipped in the WRONG UNITS for a full campaign cycle: 0.25 was set as
# "half the real-edge band's lower edge of 0.5", but validate() reports PER-BAR Sharpe, so the
# floor was 4.78 annualised -- 3.2x above the TOP of the band it was meant to sit below. These
# tests exist so the mistake is mechanical to catch rather than a docstring nobody reads.

from libs.validation.screen_admission import (  # noqa: E402
    MIN_ADMISSION_ANN_SHARPE,
    MIN_ADMISSION_BARS,
    PPY_DAILY,
)


def test_the_floor_is_derived_from_the_annualised_declaration_not_hand_set():
    """THE UNITS GUARD. The per-bar constant must be the annualised one divided by sqrt(PPY). If
    someone hand-edits the per-bar number again, this fails immediately instead of after a
    campaign returns zero survivors."""
    assert pytest.approx(
        MIN_ADMISSION_ANN_SHARPE / (PPY_DAILY ** 0.5)) == MIN_ADMISSION_OOS_SHARPE


def test_the_floor_sits_below_the_band_where_real_edge_is_observed_to_live():
    """The floor's whole justification. Its ANNUALISED value must sit under 0.5, the bottom of
    REAL_EDGE_OOS_SHARPE_BAND -- otherwise it rejects real edges for being imprecisely measured,
    which is what it did at 4.78."""
    from libs.validation.robustness_filters import REAL_EDGE_OOS_SHARPE_BAND
    assert REAL_EDGE_OOS_SHARPE_BAND[0] > MIN_ADMISSION_ANN_SHARPE


def test_a_realistic_edge_now_clears_the_floor():
    """The regression the units error caused: a true annualised Sharpe of 1.0 measured cleanly is
    squarely inside the real-edge band and MUST be admissible. Under the old floor it was not."""
    oos_per_bar = 1.0 / (PPY_DAILY ** 0.5)
    plan = admit([{"name": "real", "gates": {}, "oos_sharpe": oos_per_bar,
                   "n_bars": MIN_ADMISSION_BARS}], idle_slots=12, cost_basis="net")
    assert [a.name for a in plan.admitted] == ["real"]


def test_a_sharpe_measured_on_too_few_bars_is_blocked_for_cause():
    """Not strictness. Below ~1,460 daily bars the standard error of the OOS Sharpe is wider than
    the entire 0.5-1.5 band, so the number carries no information to admit on. Blocking is the
    honest response to an unresolvable measurement."""
    plan = admit([{"name": "short", "gates": {}, "oos_sharpe": 5.0, "n_bars": 310}],
                 idle_slots=12, cost_basis="net")
    assert not plan.admitted
    assert "insufficient_bars" in plan.blocked[0].blocked_by


def test_an_undeclared_bar_count_is_reported_unmeasured_not_passed():
    """A missing sample width is exactly how a 19x units error shipped unnoticed. It must be
    surfaced, never silently treated as adequate."""
    plan = admit([{"name": "quiet", "gates": {}, "oos_sharpe": 5.0}],
                 idle_slots=12, cost_basis="net")
    assert any("UNMEASURED sample width" in n for n in plan.notes)


def test_the_bar_floor_is_the_two_standard_error_arithmetic_not_a_taste():
    """T >= 4 * PPY / SR^2 puts a true annualised Sharpe of 1.0 two standard errors above zero."""
    assert pytest.approx(4.0 * PPY_DAILY / 1.0 ** 2, rel=0.01) == MIN_ADMISSION_BARS


class TestICIsNotPnL:
    """L0013, graduated: positive IC is not a profitable strategy.

    MEASURED: reversal and leadlag both posted positive Spearman IC and NEGATIVE gross Sharpe —
    IC lives mid-distribution while the tradeable top and bottom buckets do not carry it. The
    admission screen is where that lesson has to bite, so the ranking must key on realised
    net-of-cost performance and never on a correlation statistic.
    """

    def test_ranking_is_driven_by_oos_sharpe_not_a_correlation_field(self) -> None:
        """A row carrying a flattering `ic` must not outrank one with better OOS P&L."""
        g = dict.fromkeys(STATISTICAL_GATES, True)
        good_pnl = rank_score(g, oos_sharpe=0.80, dsr=0.9, reality_p=0.01, cost_basis="net")
        flattering_ic = rank_score({**g, "ic": True}, oos_sharpe=0.20, dsr=0.9,
                                   reality_p=0.01, cost_basis="net")
        assert good_pnl > flattering_ic

    def test_gross_numbers_are_charged_and_net_numbers_are_not(self) -> None:
        """The lesson's operative half: a candidate quoted GROSS pays the turnover charge, so a
        high-turnover signal cannot present its pre-cost number as if it were tradeable."""
        g = dict.fromkeys(STATISTICAL_GATES, True)
        gross = rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01,
                           turnover=0.60, cost_basis="gross")
        net = rank_score(g, oos_sharpe=1.0, dsr=0.9, reality_p=0.01,
                         turnover=0.60, cost_basis="net")
        assert gross < net, "a gross-quoted candidate must be charged for its turnover"
