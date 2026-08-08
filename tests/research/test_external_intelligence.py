"""BEHAVIORAL tests for the external-intelligence ledgers.

Three properties, each of which the desk would otherwise get wrong silently:

    a fragment recorded as a transcript             video_intelligence
    a large number mistaken for evidence            return_claims
    a specified capability mistaken for an adopted one   competitor_coverage
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from libs.research.competitor_coverage import (
    ADOPTION_DIMENSIONS,
    EngineCoverage,
    adoption_status,
    coverage_score,
    residual_frontier,
    superiority,
)
from libs.research.return_claims import (
    TRANSFERABLE_SOURCES,
    ReturnClaim,
    decompose,
    evidence_weight,
    priority,
    transferable_share,
)
from libs.research.return_claims import summarise as claims_summary
from libs.research.video_intelligence import (
    MIN_STATUS_FOR_EXTRACTION,
    ChannelCoverage,
    VideoRecord,
    effective_independent_sources,
    exhausted,
    source_roi,
    unresolved_high_value,
)
from libs.research.video_intelligence import summarise as video_summary

ROOT = Path(__file__).resolve().parents[2]


def _vid(**kw) -> VideoRecord:
    base: dict[str, object] = {"video_id": "v1", "channel": "c", "title": "t",
                               "transcript_status": "FULL", "start_verified": True,
                               "end_verified": True, "mechanisms_extracted": 3}
    base.update(kw)
    return VideoRecord(**base)  # type: ignore[arg-type]


# =========================================================== video: partial is never full

def test_a_partial_transcript_is_not_extractable() -> None:
    """THE HEADLINE DISCIPLINE. An extraction from a fragment looks identical downstream to an
    extraction from a complete transcript, and no later check can separate them."""
    assert not _vid(transcript_status="PARTIAL").extractable
    assert not _vid(transcript_status="DESCRIPTION_ONLY").extractable
    assert _vid(transcript_status="NEAR_FULL").extractable
    assert _vid(transcript_status="FULL").extractable


def test_a_full_transcript_with_an_unchecked_end_is_still_refused() -> None:
    """Truncation at the END is the commonest silent failure: the conclusions, the failures and
    the caveats all live in the last ten minutes."""
    assert not _vid(transcript_status="FULL", end_verified=False).extractable
    assert not _vid(transcript_status="FULL", start_verified=False).extractable


def test_an_invalid_transcript_status_cannot_be_recorded() -> None:
    with pytest.raises(ValueError, match="transcript_status must be"):
        _vid(transcript_status="MOSTLY")


def test_extractions_from_fragments_are_the_headline_finding() -> None:
    c = ChannelCoverage(channel="c", enumeration_complete=True, videos=(
        _vid(video_id="ok"),
        _vid(video_id="frag", transcript_status="PARTIAL", mechanisms_extracted=4)))
    rep = video_summary([c])
    assert len(rep["extractions_from_incomplete_transcripts"]) == 1   # type: ignore[arg-type]
    assert "below NEAR_FULL" in str(rep["headline"])
    assert MIN_STATUS_FOR_EXTRACTION == "NEAR_FULL"


# ------------------------------------------------------------------ exhaustion is temporary

def test_incomplete_enumeration_cannot_be_exhausted() -> None:
    done, why = exhausted(ChannelCoverage(channel="c", videos=(_vid(),)))
    assert done is False
    assert "LOWER bound" in why


def test_a_fully_consumed_channel_is_only_CURRENTLY_exhausted() -> None:
    c = ChannelCoverage(channel="c", enumeration_complete=True, last_swept="2026-08-08",
                        videos=(_vid(),))
    done, why = exhausted(c)
    assert done is True
    assert "CURRENTLY exhausted" in why and "new uploads reopen" in why


def test_a_blocked_video_blocks_exhaustion_and_is_named_blocked() -> None:
    c = ChannelCoverage(channel="c", enumeration_complete=True, videos=(
        _vid(), _vid(video_id="v2", transcript_status="UNAVAILABLE", mechanisms_extracted=0,
                    start_verified=False, end_verified=False,
                    unresolved_reason="TRANSCRIPT_DISABLED", estimated_value=9.0)))
    done, why = exhausted(c)
    assert done is False
    assert "externally blocked" in why
    assert "never covered" in why
    q = unresolved_high_value([c])
    assert q and q[0]["video_id"] == "v2"


def test_the_retry_queue_is_ranked_by_value_not_by_order() -> None:
    c = ChannelCoverage(channel="c", enumeration_complete=True, videos=(
        _vid(video_id="cheap", transcript_status="UNAVAILABLE", start_verified=False,
             end_verified=False, mechanisms_extracted=0, unresolved_reason="FETCH_FAILED",
             estimated_value=1.0),
        _vid(video_id="dear", transcript_status="UNAVAILABLE", start_verified=False,
             end_verified=False, mechanisms_extracted=0, unresolved_reason="FETCH_FAILED",
             estimated_value=50.0)))
    assert unresolved_high_value([c])[0]["video_id"] == "dear"


def test_falling_source_roi_lowers_cadence_and_never_deletes() -> None:
    c = ChannelCoverage(channel="c", enumeration_complete=True, processing_cost_units=100.0,
                        videos=(_vid(residuals_new=1),))
    roi, why = source_roi(c)
    assert roi == pytest.approx(0.01)
    assert "LOWER THE CADENCE, do not delete" in why


def test_popularity_is_diffusion_not_replication() -> None:
    """Twenty creators describing an RSI system are usually one mechanism copied nineteen times."""
    eff, why = effective_independent_sources("rsi_oversold", dict.fromkeys(
        [f"creator{i}" for i in range(20)], 0.05))
    assert eff == pytest.approx(1.0)
    assert "DIFFUSION" in why
    eff2, why2 = effective_independent_sources("x", {"a": 0.9, "b": 0.9, "c": 0.9})
    assert eff2 == pytest.approx(2.7)
    assert "independent discovery raises" in why2


# ========================================== claims: a big number is urgency, not evidence

def _claim(**kw) -> ReturnClaim:
    base: dict[str, object] = {
        "subject": "X", "source": "s", "observed_at": "2026-01-01",
        "evidence_class": "SELF_REPORTED", "reported_return": 2.0, "horizon_days": 365.0,
        "mechanism": "funding-carry unwind on crowded perp longs",
        "attribution": {"ALPHA": 0.6, "BETA": 0.4}}
    base.update(kw)
    return ReturnClaim(**base)  # type: ignore[arg-type]


def test_a_verified_modest_return_outranks_a_self_reported_enormous_one() -> None:
    """THE NAMED CASE. If this inverts, the module has started sorting on the headline number."""
    modest = _claim(subject="verified_neutral", evidence_class="VERIFIED", reported_return=0.5,
                    net_of_costs=True, realised=True, flows_disclosed=True,
                    attribution={"ALPHA": 1.0})
    huge = _claim(subject="selfreported_10x", evidence_class="SELF_REPORTED",
                  reported_return=10.0, attribution={"LEVERAGE": 0.7, "BETA": 0.3},
                  mechanism="leveraged long")
    a, _ = priority(modest)
    b, _ = priority(huge)
    assert a > b, f"the self-reported 1000% outranked the verified 50%: {a} vs {b}"


def test_leverage_and_beta_are_not_transferable() -> None:
    c = _claim(attribution={"LEVERAGE": 0.5, "BETA": 0.5}, mechanism="3x long")
    share, _ = transferable_share(c)
    assert share == pytest.approx(0.0)
    assert frozenset({"ALPHA", "CARRY", "CONVEXITY"}) == TRANSFERABLE_SOURCES


def test_a_claim_with_no_mechanism_is_worth_nothing_to_copy() -> None:
    c = _claim(mechanism="   ", attribution={"ALPHA": 1.0})
    share, why = transferable_share(c)
    assert share == 0.0
    assert "cannot be reproduced even if it was entirely real" in why


def test_the_unattributed_remainder_is_named_unverifiable() -> None:
    d = decompose(_claim(attribution={"ALPHA": 0.2}))
    assert d["UNVERIFIABLE"] == pytest.approx(0.8)
    _, why = transferable_share(_claim(attribution={"ALPHA": 0.2}))
    assert "the desk does not know what produced it" in why


def test_a_backtest_is_weaker_evidence_than_a_self_report() -> None:
    """A backtest is a claim about the past made by whoever chose the parameters."""
    assert evidence_weight(_claim(evidence_class="BACKTEST")) < \
        evidence_weight(_claim(evidence_class="SELF_REPORTED"))


def test_disclosure_gaps_discount_the_evidence_weight() -> None:
    full = _claim(evidence_class="VERIFIED", net_of_costs=True, realised=True,
                  flows_disclosed=True)
    thin = _claim(evidence_class="VERIFIED")
    assert evidence_weight(full) > evidence_weight(thin) * 2


def test_an_unknown_return_source_cannot_be_recorded() -> None:
    with pytest.raises(ValueError, match="unknown return source"):
        _claim(attribution={"VIBES": 1.0})


def test_a_two_week_horizon_is_penalised_not_annualised_into_glory() -> None:
    short = _claim(horizon_days=14.0, reported_return=0.5)
    long_ = _claim(horizon_days=365.0, reported_return=0.5)
    assert priority(short)[0] < priority(long_)[0]


def test_the_claims_note_states_the_law() -> None:
    rep = claims_summary([_claim()])
    assert "raises investigation URGENCY and never the evidence bar" in str(rep["note"])


# ================================= coverage: specified is not adopted

def test_adoption_requires_all_six_dimensions() -> None:
    e = EngineCoverage(engine="x", dimensions_met=tuple(ADOPTION_DIMENSIONS),
                       measured_value="+3bp/day")
    assert adoption_status(e)[0] == "ADOPTED"


def test_identified_and_specified_reports_the_first_missing_dimension() -> None:
    e = EngineCoverage(engine="x", dimensions_met=("IDENTIFIED", "SPECIFIED"))
    status, why = adoption_status(e)
    assert status == "NOT_ADOPTED"
    assert "first missing dimension is IMPLEMENTED" in why
    assert "a document and no economics" in why


def test_verified_but_not_live_is_edge_sitting_still() -> None:
    e = EngineCoverage(engine="x",
                       dimensions_met=("IDENTIFIED", "SPECIFIED", "IMPLEMENTED", "VERIFIED"))
    _, why = adoption_status(e)
    assert "edge sitting still while it decays" in why


def test_a_broader_specification_is_the_weakest_superiority_claim() -> None:
    claim, why = superiority("x", our_dimensions=("IDENTIFIED", "SPECIFIED"),
                             external_evidence_class="SELF_REPORTED")
    assert claim == "DESIGN_SUPERIORITY"
    assert "loses to a narrow one that does" in why


def test_live_economic_superiority_requires_measured_economics() -> None:
    claim, _ = superiority("x", our_dimensions=tuple(ADOPTION_DIMENSIONS),
                           external_evidence_class="VERIFIED", our_measured_value="+40bp")
    assert claim == "LIVE_ECONOMIC_SUPERIORITY"
    claim2, why2 = superiority("x", our_dimensions=("IDENTIFIED", "SPECIFIED", "IMPLEMENTED",
                                                   "VERIFIED"),
                               external_evidence_class="VERIFIED")
    assert claim2 == "IMPLEMENTATION_SUPERIORITY"
    assert "settles nothing economically" in why2


def test_coverage_is_reported_per_dimension_not_as_one_percentage() -> None:
    rep = coverage_score([EngineCoverage(engine="a", dimensions_met=("IDENTIFIED",)),
                          EngineCoverage(engine="b", dimensions_met=tuple(ADOPTION_DIMENSIONS))])
    assert rep["by_dimension"]["IDENTIFIED"] == 2
    assert rep["by_dimension"]["LIVE"] == 1
    assert "averaging a live capability with a paragraph" in str(rep["note"])


def test_the_residual_frontier_ranks_by_value_per_cost() -> None:
    rows = residual_frontier([
        EngineCoverage(engine="cheap_win", dimensions_met=("IDENTIFIED", "SPECIFIED"),
                       expected_close_value=1.0, estimated_cost_units=1.0),
        EngineCoverage(engine="expensive", dimensions_met=("IDENTIFIED", "SPECIFIED"),
                       expected_close_value=2.0, estimated_cost_units=100.0)])
    assert rows[0]["engine"] == "cheap_win"


def test_unknown_external_usage_is_permitted_and_never_invented() -> None:
    e = EngineCoverage(engine="x", external_uses="UNKNOWN")
    assert e.external_uses == "UNKNOWN"
    with pytest.raises(ValueError, match="external_uses must be"):
        EngineCoverage(engine="y", external_uses="PROBABLY")


# ================================================================ the shipped matrix + script

def test_the_shipped_matrix_covers_every_engine_the_spec_names() -> None:
    doc = json.loads((ROOT / "docs/research/COMPETITOR_COVERAGE.json").read_text("utf-8"))
    names = {e["engine"] for e in doc["engines"]}
    for required in ("crypto_beta", "dip_rebound_timing", "profit_harvesting",
                     "cross_sectional_momentum", "protocol_carry_staking",
                     "prediction_market_trading", "unconventional_feature_mining",
                     "participant_broker_behaviour", "live_learning", "execution_discipline"):
        assert required in names, f"{required} missing from the coverage matrix"
    assert len(names) >= 28


def test_the_shipped_matrix_claims_no_adoption_it_cannot_evidence() -> None:
    """Nothing on this desk has produced a euro, so nothing may be LIVE or ECONOMICALLY_VALIDATED.
    A matrix that opened at 'mostly adopted' would be measuring the author's optimism."""
    doc = json.loads((ROOT / "docs/research/COMPETITOR_COVERAGE.json").read_text("utf-8"))
    for e in doc["engines"]:
        dims = set(e.get("dimensions_met") or ())
        assert "LIVE" not in dims, f"{e['engine']} claims LIVE with no fills on this desk"
        assert "ECONOMICALLY_VALIDATED" not in dims, f"{e['engine']} claims measured economics"


def test_the_script_runs_and_writes_its_artifact(tmp_path) -> None:
    out = tmp_path / "external_intel.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/run_external_intel.py"),
                        "--out", str(out)], cwd=ROOT, capture_output=True, text=True,
                       timeout=300, check=False)
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text("utf-8"))
    assert doc["competitor_coverage"]["coverage_score"]["engines"] >= 28
    assert "NEXT" in r.stdout


def test_the_gpt_mission_forbids_fabrication_and_preserves_kimi() -> None:
    """Two properties of the seat that must not drift: it may not invent transcript content, and
    its existence may not be used to shrink another hunter."""
    src = (ROOT / "ops/gpt_video_hunter_prompt.txt").read_text("utf-8")
    assert "NEVER FABRICATE TRANSCRIPT CONTENT" in src
    assert "PARTIAL IS NEVER FULL" in src
    assert "Kimi keeps its entire mandate unchanged" in src
    assert "boundary, not a hurdle" in src.lower() or "BOUNDARY, NOT A HURDLE" in src
