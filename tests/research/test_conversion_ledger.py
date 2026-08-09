"""The feedback loop, and the three ways a calibration number lies.

test_in_sample_and_out_of_sample_are_reported_separately is the one that matters. A calibration
computed on the set the weights were fitted to is guaranteed to look good and means nothing --
which is the same defect, one level up, that the whole ledger exists to fix.
"""
from __future__ import annotations

import pytest

from libs.research.conversion_ledger import Entry, calibration, load, record, seed


def _e(ident: str, score: float, outcome: str, cohort: str = "out_of_sample") -> Entry:
    return Entry(ident=ident, title=ident, source="t", score=score,
                 outcome=outcome, cohort=cohort)


def test_an_unknown_outcome_is_rejected_at_construction():
    """A free-text outcome field would fill with 'maybe' and 'partially' within a month, and the
    conversion rate would stop meaning anything."""
    with pytest.raises(ValueError, match="outcome"):
        Entry(ident="x", title="x", source="t", score=1.0, outcome="sort_of")


def test_the_ledger_is_append_only(tmp_path):
    p = tmp_path / "l.jsonl"
    record(_e("a", 8.0, "converted"), path=p)
    record(_e("b", 2.0, "read_no_value"), path=p)
    assert [x.ident for x in load(p)] == ["a", "b"]


def test_a_malformed_row_does_not_take_down_the_audit(tmp_path):
    p = tmp_path / "l.jsonl"
    record(_e("good", 8.0, "converted"), path=p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{not json at all\n")
    assert [x.ident for x in load(p)] == ["good"]


# ------------------------------------------------------------------- what calibration excludes

def test_unread_items_are_excluded_entirely(tmp_path):
    """An item never read carries no information about the ranker. Counting it as a failure would
    punish exactly the high-scored backlog the ranker is trying to build."""
    p = tmp_path / "l.jsonl"
    for i in range(12):
        record(_e(f"hi{i}", 9.0, "queued_unread"), path=p)
    record(_e("read", 9.0, "converted"), path=p)
    rep = calibration(p)
    assert rep["n_scored"] == 1


def test_in_sample_and_out_of_sample_are_reported_separately(tmp_path):
    """THE TEST THAT MATTERS. The seeded batch is the set the weights were read off, so its
    calibration is guaranteed good and is evidence of nothing. Only out-of-sample lift counts."""
    p = tmp_path / "l.jsonl"
    for i in range(6):
        record(_e(f"is{i}", 9.0, "converted", cohort="in_sample"), path=p)
    for i in range(6):
        record(_e(f"oos{i}", 9.0, "read_no_value", cohort="out_of_sample"), path=p)
    rep = calibration(p)
    assert rep["in_sample"]["convert_rate_high"] == 1.0
    assert rep["out_of_sample"]["convert_rate_high"] == 0.0
    assert rep["in_sample"]["n"] == 6 and rep["out_of_sample"]["n"] == 6


def test_too_few_outcomes_reports_unmeasured_rather_than_a_number(tmp_path):
    """A lift computed from four observations is noise wearing a decimal point."""
    p = tmp_path / "l.jsonl"
    record(_e("a", 9.0, "converted"), path=p)
    record(_e("b", 1.0, "read_no_value"), path=p)
    assert "UNMEASURED" in calibration(p)["verdict"]


# ----------------------------------------------------------------------- what it concludes

def test_a_ranker_that_works_reads_as_calibrated(tmp_path):
    p = tmp_path / "l.jsonl"
    for i in range(8):
        record(_e(f"hi{i}", 9.0, "converted"), path=p)
    for i in range(8):
        record(_e(f"lo{i}", 1.0, "read_no_value" if i else "converted"), path=p)
    rep = calibration(p)
    assert rep["out_of_sample"]["lift"] >= 1.5
    assert "CALIBRATED" in rep["verdict"]


def test_a_ranker_that_does_not_work_says_so(tmp_path):
    """The outcome that must not be softened. If high scores do not convert more often, the
    weights were fitted to the old batch and the honest move is to re-derive them."""
    p = tmp_path / "l.jsonl"
    for i in range(8):
        record(_e(f"hi{i}", 9.0, "converted" if i < 4 else "read_no_value"), path=p)
    for i in range(8):
        record(_e(f"lo{i}", 1.0, "converted" if i < 4 else "read_no_value"), path=p)
    rep = calibration(p)
    assert rep["out_of_sample"]["lift"] == 1.0
    assert "NOT CALIBRATED" in rep["verdict"]


def test_no_low_scored_reads_is_unmeasurable_not_infinite(tmp_path):
    """Without a baseline there is no lift. Reporting one would divide by zero and call it skill."""
    p = tmp_path / "l.jsonl"
    for i in range(12):
        record(_e(f"hi{i}", 9.0, "converted"), path=p)
    assert "UNMEASURABLE" in calibration(p)["verdict"]


# ------------------------------------------------------------------------------- the seed

def test_seeding_is_idempotent(tmp_path):
    p = tmp_path / "l.jsonl"
    first = seed(p)
    assert first > 0
    assert seed(p) == 0
    assert len(load(p)) == first


def test_the_seed_is_labelled_in_sample(tmp_path):
    """Seeded rows ARE the fitting set. Mislabelling them out-of-sample would manufacture a
    calibration result out of the very data the weights came from."""
    p = tmp_path / "l.jsonl"
    seed(p)
    assert all(e.cohort == "in_sample" for e in load(p))
