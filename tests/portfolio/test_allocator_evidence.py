"""The Allocator-V2 evidence vector: every term named, UNMEASURED reads 1.0, lineage
concentration rises for two same-lineage sleeves and is heat-neutral, the consumer's read
degrades to nothing on an absent or stale document."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.portfolio import allocator_evidence as AE

LAW_TERMS = ("posterior_edge", "confidence", "regime_relevance", "diversification", "capacity",
             "liquidity", "execution_quality", "alpha_half_life", "impact", "financing_stress",
             "common_hidden_exposures", "lineage_concentration", "tail_risk")


def test_every_term_of_the_law_is_named_and_declared_where_it_is_priced():
    names = {s.name for s in AE.TERM_SPECS}
    assert set(LAW_TERMS) <= names and "research_roi" in names
    for s in AE.TERM_SPECS:
        assert s.role in ("factor", "deduction") and s.where
        if not s.priced_inside_allocator:
            assert s.consumed_as, s.name


def test_unmeasured_reads_exactly_one_everywhere():
    v = AE.build_vector("s", family="f", symbol="EURUSD", lineage="f|EUR+USD|H1",
                        lineage_term=None, roi_term=None, financing=None,
                        financing_charged_in_replay=None)
    assert v.composite() == 1.0 and v.consumed_tilt() == 1.0 and v.n_measured() == 0
    d = v.as_dict()
    assert all(t["factor"] == 1.0 and t["status"] == AE.UNMEASURED for t in d["terms"].values())
    assert d["financing_cost_r_per_day"] is None
    assert AE.roi_factor(None, [0.1, 0.2]).factor == 1.0
    assert AE.roi_factor({"roi": 0.5, "roi_status": "UNMEASURED", "judged": 100},
                         [0.1, 0.2]).factor == 1.0


def test_lineage_concentration_rises_for_two_same_lineage_sleeves_and_is_heat_neutral():
    lin = {"a": "carry|CHF+NOK|H1", "b": "carry|CHF+NOK|H1", "c": "gap|EUR+ZAR|H1"}
    alone = AE.lineage_shares({"a": 0.1, "c": 0.1}, {"a": lin["a"], "c": lin["c"]})
    both = AE.lineage_shares({"a": 0.1, "b": 0.1, "c": 0.1}, lin)
    assert alone["a"] == pytest.approx(0.5) and both["a"] > alone["a"]
    # a candidate OUTSIDE the book reads the share its lineage already holds
    cand = AE.lineage_shares({"a": 0.1, "c": 0.1}, {"a": lin["a"], "c": lin["c"], "b": lin["b"]})
    assert cand["b"] == pytest.approx(0.5)
    terms = AE.lineage_factors({"a": 0.1, "b": 0.1, "c": 0.1}, lin)
    assert terms["a"].value == pytest.approx(2.0 / 3.0)
    assert terms["c"].value == pytest.approx(1.0 / 3.0)
    # the unique lineage is tilted UP, the shared one DOWN, and the book's heat-weighted mean
    # tilt is exactly 1.0: capital moves between lineages, the total is untouched
    assert terms["c"].factor > 1.0 > terms["a"].factor
    mean = sum(0.1 * terms[n].factor for n in lin) / 0.3
    assert mean == pytest.approx(1.0)
    # a book that is ONE lineage everywhere normalises back to 1.0 for every sleeve
    one = AE.lineage_factors({"a": 0.1, "b": 0.2}, {"a": "x", "b": "x"})
    assert all(t.factor == pytest.approx(1.0) for t in one.values())
    assert AE.lineage_key("Carry", "CHFNOK", ["NOK", "CHF"], "h1") == "carry|CHF+NOK|H1"
    assert AE.lineage_key("", "US500", None, "") == "unspecified|US500|?"


def test_roi_prior_ranks_measured_mechanisms_two_sidedly_and_shrinks_by_judged_count():
    rois = [0.0, 0.05, 0.10]
    top = AE.roi_factor({"roi": 0.10, "roi_status": "MEASURED", "judged": 400}, rois)
    bottom = AE.roi_factor({"roi": 0.0, "roi_status": "MEASURED", "judged": 400}, rois)
    few = AE.roi_factor({"roi": 0.10, "roi_status": "MEASURED", "judged": 2}, rois)
    assert top.factor > 1.0 > bottom.factor
    assert 1.0 < few.factor < top.factor
    assert bottom.factor >= 0.5 and top.factor <= 1.5
    neg = AE.roi_factor({"roi": 0.10, "roi_status": "MEASURED", "judged": 400,
                         "verdict": "NEGATIVE_KNOWLEDGE"}, rois)
    assert neg.factor < 1.0
    assert AE.roi_factor({"roi": 0.1, "roi_status": "MEASURED", "judged": 9}, [0.1]).factor == 1.0
    assert AE.match_mechanism("EURZAR_overnight_gap_decay_asia", "overnight_gap_decay",
                              ["carry", "overnight_gap_decay", "generic"]) == "overnight_gap_decay"
    assert AE.match_mechanism("audcad_discovered_asia_p_7c99", "discovered_asia_p",
                              ["discovered", "UNKNOWN"]) == "discovered"
    assert AE.match_mechanism("gold_asia", "session_bracket", ["carry"]) is None


def test_consumed_tilt_is_bounded_and_financing_is_a_signed_level_not_a_factor():
    roi = AE.Term("research_roi", 0.1, AE.MEASURED, 1.5)
    lin = AE.Term("lineage_concentration", 0.0, AE.MEASURED, 1.6)
    fin = AE.financing_term(-0.004, 1.0, 0.10)          # a carry CREDIT
    v = AE.build_vector("s", family="carry", symbol="CHFNOK", lineage="l", lineage_term=lin,
                        roi_term=roi, financing=fin, financing_charged_in_replay=False)
    assert v.consumed_tilt() == AE.TILT_HI                 # 2.4 clipped to 2.0
    assert v.financing_cost_r_per_day == pytest.approx(-0.004)
    assert v.term("financing_stress").factor == 1.0        # consumed as a shift, never twice
    assert AE.financing_term(None, 1.0, 0.1).status == AE.UNMEASURED


def test_the_consumers_read_degrades_to_nothing_on_absent_stale_or_malformed_documents():
    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    assert AE.consumed_inputs(None, now=now)[0] == {}
    assert AE.consumed_inputs({"kind": "report"}, now=now)[0] == {}
    stale = {"kind": "evidence", "at": (now - timedelta(hours=30)).isoformat(),
             "sleeves": {"a": {"lineage_factor": 1.2}}}
    rows, why = AE.consumed_inputs(stale, now=now)
    assert rows == {} and "old" in why
    fresh = {"kind": "evidence", "at": (now - timedelta(minutes=5)).isoformat(),
             "sleeves": {"a": {"lineage_factor": 9.0, "financing_cost_r_per_day": 0.01,
                               "financing_charged_in_replay": False},
                         "b": {"lineage_factor": "junk", "financing_cost_r_per_day": None}}}
    rows, _ = AE.consumed_inputs(fresh, now=now)
    assert rows["a"]["lineage_factor"] == AE.TILT_HI
    assert rows["a"]["financing_cost_r_per_day"] == 0.01
    assert rows["b"]["lineage_factor"] == 1.0 and rows["b"]["financing_cost_r_per_day"] is None
    by_mech, _ = AE.roi_factors_by_mechanism(
        {"kind": "evidence", "by_mechanism": {
            "carry": {"roi": 0.2, "roi_status": "MEASURED", "judged": 100},
            "gap": {"roi": 0.0, "roi_status": "MEASURED", "judged": 100},
            "x": {"roi": None, "roi_status": "UNMEASURED"}}})
    assert by_mech["carry"].factor > 1.0 > by_mech["gap"].factor and by_mech["x"].factor == 1.0
    assert AE.roi_factors_by_mechanism(None)[0] == {}


def test_book_vector_reports_lineage_hhi_and_coverage():
    lin = {"a": "l1", "b": "l1", "c": "l2"}
    terms = AE.lineage_factors({"a": 0.1, "b": 0.1, "c": 0.2}, lin)
    vs = [AE.build_vector(n, family="f", symbol="S", lineage=lin[n], lineage_term=terms[n],
                          roi_term=None, financing=None, financing_charged_in_replay=None)
          for n in lin]
    b = AE.book_vector(vs, {"a": 0.1, "b": 0.1, "c": 0.2})
    assert b["n_lineages_funded"] == 2 and b["lineage_hhi"] == pytest.approx(0.5)
    assert b["terms_measured_by_name"]["lineage_concentration"] == 3
    assert b["terms_measured_by_name"]["tail_risk"] == 0
    assert b["heat_weighted_consumed_tilt"] == pytest.approx(1.0)
