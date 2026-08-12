"""Gate items 29/32/33: copy friction, extreme-return attribution, and the blow-up library."""
from __future__ import annotations

from pathlib import Path

from libs.research.performer_forensics import (
    ATTRIBUTIONS,
    FAILURE_MODES,
    CopyLeg,
    Performer,
    classify_failure,
    copy_friction,
    decompose,
    extract_components,
    rescue_analysis,
)


# ------------------------------------------------------------------ item 29: copy friction
def test_item29_a_thin_edge_is_destroyed_by_the_copy_pipeline() -> None:
    """II-8. Do not assume the follower receives the leader's return -- this is the test."""
    # A 40bps leader edge that decays at 1bp/s. The copy pipeline costs 35s of decay (35bps) plus
    # 20bps of round-trip slippage and fees -- 55bps of friction against 40bps of edge.
    out = copy_friction([CopyLeg(leader_gross_return=0.004, publication_delay_s=20,
                                 detection_delay_s=10, execution_delay_s=5,
                                 adverse_move_bps_per_s=1.0, entry_slippage_bps=6,
                                 exit_slippage_bps=6, fee_bps_round_trip=8)])
    assert out["verdict"] == "DESTROYED_BY_COPY_FRICTION"
    assert out["follower_total_return"] < 0 < out["leader_total_return"]


def test_item29_a_fat_slow_edge_survives() -> None:
    out = copy_friction([CopyLeg(leader_gross_return=0.08, publication_delay_s=30,
                                 adverse_move_bps_per_s=0.05, entry_slippage_bps=5,
                                 exit_slippage_bps=5, fee_bps_round_trip=8, profit_share=0.10)])
    assert out["verdict"] == "SURVIVES_COPY_FRICTION"
    assert 0 < out["follower_total_return"] < out["leader_total_return"]


def test_item29_profit_share_is_charged_on_gross_winners_not_net_performance() -> None:
    """THE ASYMMETRY. A leader making +10% then -8% nets ~1.2%; the follower pays the share on
    the +10% and absorbs the -8% in full, so the follower can LOSE while the leader's headline
    is positive."""
    legs = [CopyLeg(leader_gross_return=0.10, profit_share=0.20),
            CopyLeg(leader_gross_return=-0.08, profit_share=0.20)]
    out = copy_friction(legs)
    assert out["leader_total_return"] == 0.02
    assert out["follower_total_return"] == 0.0                # 0.10 - 0.02 share, then -0.08
    paid = [leg["profit_share_paid"] for leg in out["legs"]]
    assert paid[0] == -0.02 and paid[1] == 0.0, "no share is credited back on a losing leg"


def test_item29_latency_is_charged_as_an_adverse_move() -> None:
    """A leader whose edge is a 30-second reaction does not survive a 90-second copy pipeline,
    and no fee negotiation repairs that."""
    fast = copy_friction([CopyLeg(leader_gross_return=0.02, publication_delay_s=1,
                                  adverse_move_bps_per_s=2.0)])
    slow = copy_friction([CopyLeg(leader_gross_return=0.02, publication_delay_s=60,
                                  adverse_move_bps_per_s=2.0)])
    assert slow["follower_total_return"] < fast["follower_total_return"]


def test_item29_no_legs_is_unmeasured_not_a_survival_verdict() -> None:
    assert copy_friction([])["status"] == "UNMEASURED"


# ------------------------------------------------------------------ item 32: decomposition
def test_item32_a_short_window_is_a_structural_short_sample_attribution() -> None:
    out = decompose(Performer(ident="a", platform="p", headline_return=3.0, window_days=21))
    assert "SHORT_SAMPLE" in [a["class"] for a in out["attribution"]]
    assert out["verdict"] == "HIGH_VOI_RESEARCH_TRIGGER"


def test_item32_unrepresented_open_losses_are_named_as_an_accounting_artifact() -> None:
    """The classic marketplace artifact: realised wins booked, losers carried open forever."""
    out = decompose(Performer(ident="a", platform="p", headline_return=4.0, window_days=400,
                              open_losses_represented=False))
    assert out["leading_attribution"] == "ROI_ACCOUNTING_ARTIFACT"
    assert any("monotone equity curve" in f for f in out["structural_flags"])


def test_item32_big_return_with_tiny_drawdown_reads_as_martingale() -> None:
    out = decompose(Performer(ident="a", platform="p", headline_return=2.5, window_days=200,
                              max_drawdown=0.02))
    assert "MARTINGALE" in [a["class"] for a in out["attribution"]]
    assert any("one bad day" in f for f in out["structural_flags"])


def test_item32_high_leverage_attributes_to_leverage_and_demands_the_deleveraged_edge() -> None:
    """III-8: do not attempt to match headline returns through leverage alone."""
    out = decompose(Performer(ident="a", platform="p", headline_return=5.0, window_days=300,
                              max_leverage=20.0))
    assert "LEVERAGE" in [a["class"] for a in out["attribution"]]
    assert any("DELEVERAGED" in f for f in out["structural_flags"])


def test_item32_nothing_verified_leaves_the_record_unverified() -> None:
    """An extreme return with nothing checked is a research trigger with a big number attached."""
    out = decompose(Performer(ident="a", platform="p", headline_return=9.0))
    assert out["status"] == "UNVERIFIED"
    assert out["leading_attribution"] == "UNVERIFIED"
    assert "answer the unverified stations" in out["next_action"]


def test_item32_a_fully_verified_clean_performer_becomes_a_candidate_mechanism() -> None:
    p = Performer(ident="a", platform="p", headline_return=0.4, window_days=500,
                  max_drawdown=0.18, max_leverage=1.0, largest_position_share=0.15,
                  open_losses_represented=True,
                  verified=dict.fromkeys(
                      ("public_metrics", "window", "capital_base", "leverage", "drawdown",
                       "age", "position_concentration", "open_losses_represented",
                       "roi_methodology"), True))
    out = decompose(p, evidence={"GENUINE_ALPHA": 0.7})
    assert out["status"] == "VERIFIED" and out["verdict"] == "CANDIDATE_MECHANISM"


def test_item32_an_unknown_attribution_class_is_surfaced_not_silently_dropped() -> None:
    out = decompose(Performer(ident="a", platform="p", window_days=500),
                    evidence={"VIBES": 0.9})
    assert out["unknown_classes"] == ["VIBES"]


def test_item32_never_dismisses_and_never_believes() -> None:
    out = decompose(Performer(ident="a", platform="p", headline_return=50.0))
    assert "NOT A SURVIVOR VERDICT" in out["law"] and "too-good-to-be-true" in out["law"]


def test_attribution_classes_cover_the_mandate_list() -> None:
    for k in ("GENUINE_ALPHA", "LEVERAGE", "MARTINGALE", "SURVIVORSHIP",
              "ROI_ACCOUNTING_ARTIFACT", "NOVEL_MECHANISM"):
        assert k in ATTRIBUTIONS


# ------------------------------------------------------------------ III-7 component extraction
def test_every_extracted_behaviour_becomes_its_own_hypothesis() -> None:
    """Testing only the complete original strategy scores the weld, not the mechanism."""
    p = Performer(ident="bot1", platform="p",
                  behaviour={"entry_behavior": "buys funding-negative perps",
                             "position_sizing": "martingale doubling",
                             "exit_behavior": "fixed 2% take profit"})
    out = extract_components(p)
    assert out["n_hypotheses"] == 3
    assert {h["axis"] for h in out["hypotheses"]} == {"entry_behavior", "position_sizing",
                                                     "exit_behavior"}
    assert "ablation" in out["hypotheses"][0]["test"]


def test_unextracted_axes_are_listed_as_remaining_work() -> None:
    out = extract_components(Performer(ident="b", platform="p", behaviour={"leverage": "3x"}))
    assert "capacity" in out["unextracted_axes"]


# ------------------------------------------------------------------ item 33: blow-up library
def test_item33_a_known_failure_mode_is_filed(tmp_path: Path) -> None:
    row = classify_failure(ident="bot9", mode="MARTINGALE_BLOWUP",
                           evidence="doubled into a 40% one-way move", root=tmp_path)
    assert row["failure_mode"] == "MARTINGALE_BLOWUP" and not row["taxonomy_gap"]
    assert (tmp_path / "docs/research/blowup_library.jsonl").exists()


def test_item33_an_unknown_mode_keeps_its_raw_label_as_taxonomy_evidence(tmp_path: Path) -> None:
    """Coercing it silently to UNKNOWN would erase the only signal that a NEW failure class
    exists -- which is the thing a failure library is for."""
    row = classify_failure(ident="bot9", mode="ORACLE_MANIPULATION", evidence="e",
                           root=tmp_path)
    assert row["failure_mode"] == "UNKNOWN" and row["raw_label"] == "ORACLE_MANIPULATION"
    assert row["taxonomy_gap"] is True


def test_failure_modes_cover_the_mandate_taxonomy() -> None:
    for k in ("LEVERAGE_BLOWUP", "MARTINGALE_BLOWUP", "DCA_TAIL_FAILURE", "REGIME_COLLAPSE",
              "CROWDING", "COPY_SLIPPAGE_FAILURE", "STATISTICAL_LUCK", "UNKNOWN"):
        assert k in FAILURE_MODES


# ------------------------------------------------------------------ III-9 rescue
def test_removing_the_failure_component_can_preserve_a_real_edge() -> None:
    """A real edge welded to a martingale is still a real edge."""
    out = rescue_analysis(ident="bot9", failure_mode="MARTINGALE_BLOWUP", component="sizing",
                          with_component=-0.4, without_component=0.03, n_obs=500)
    assert out["verdict"] == "EDGE_SURVIVES_COMPONENT_REMOVAL"


def test_a_rescue_creates_a_new_search_accounting_entry() -> None:
    """A repaired candidate gets NO discount for having been repaired."""
    out = rescue_analysis(ident="b", failure_mode="X", component="c",
                          with_component=-0.1, without_component=0.02, n_obs=500)
    assert "NEW SEARCH" in out["search_accounting"]


def test_an_underpowered_rescue_is_never_read_as_a_positive_result() -> None:
    """A rescue looks like good news, and good news is what gets waved through."""
    out = rescue_analysis(ident="b", failure_mode="X", component="c",
                          with_component=-0.1, without_component=0.02, n_obs=12)
    assert out["verdict"] == "UNDERPOWERED_RESCUE" and "power_warning" in out


def test_no_edge_underneath_is_reported_honestly() -> None:
    out = rescue_analysis(ident="b", failure_mode="X", component="c",
                          with_component=-0.1, without_component=-0.05, n_obs=500)
    assert out["verdict"] == "NO_EDGE_TO_RESCUE"


def test_a_missing_arm_is_unmeasured_never_a_rescue() -> None:
    out = rescue_analysis(ident="b", failure_mode="X", component="c",
                          with_component=None, without_component=0.02)
    assert out["verdict"] == "UNMEASURED"
