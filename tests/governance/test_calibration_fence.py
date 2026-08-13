"""L1.29 calibration fence -- the desk scores its own confidence, or its confidence is fiction."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.self_improvement import forecast_calibration as fc


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "_LOG", tmp_path / "forecast_log.json")
    return tmp_path


def test_overdue_flags_ungraded_predictions(store):
    past = (datetime.now(tz=UTC) - timedelta(days=2)).isoformat()
    fc.log_forecast("alpha:x", 0.7, "alpha_survival", resolve_by=past, claim="x survives 30d")
    fc.log_forecast("alpha:y", 0.6, "alpha_survival",
                    resolve_by=(datetime.now(tz=UTC) + timedelta(days=9)).isoformat())
    od = fc.overdue()
    assert [o["key"] for o in od] == ["alpha:x"]      # future deadline is not overdue


def test_resolved_forecast_is_never_overdue(store):
    past = (datetime.now(tz=UTC) - timedelta(days=2)).isoformat()
    fc.log_forecast("k", 0.8, "alpha_survival", resolve_by=past)
    fc.resolve("k", outcome=True)
    assert fc.overdue() == []


def test_shrinkage_withheld_below_five_outcomes(store):
    fc.log_forecast("a", 0.9, "eng")
    fc.resolve("a", outcome=False)
    adj = fc.calibrated_confidence(0.9)
    assert adj["applied"] is False
    assert adj["adjusted"] == 0.9                    # noise-based correction is worse than none
    assert "insufficient" in adj["why"]


_SOON = (datetime.now(tz=UTC) + timedelta(days=30)).isoformat()


def test_overconfident_desk_gets_shrunk(store):
    # Five PRE-REGISTERED forecasts at p=0.9 that all FAILED -> bias +0.9, wildly over-confident.
    for i in range(5):
        fc.log_forecast(f"f{i}", 0.9, "alpha_survival", resolve_by=_SOON, claim=f"claim {i}")
        fc.resolve(f"f{i}", outcome=False)
    rep = fc.report()
    assert rep["bias_label"] == "over-confident"
    adj = fc.calibrated_confidence(0.8)
    assert adj["applied"] is True
    assert adj["adjusted"] < 0.8                     # the loop is CLOSED, not merely reported
    assert adj["adjusted"] >= 0.0                    # and clamped


def test_underconfident_desk_gets_raised(store):
    for i in range(5):
        fc.log_forecast(f"g{i}", 0.2, "alpha_survival", resolve_by=_SOON, claim=f"g claim {i}")
        fc.resolve(f"g{i}", outcome=True)
    assert fc.report()["bias_label"] == "under-confident"
    adj = fc.calibrated_confidence(0.5)
    assert adj["adjusted"] > 0.5                     # timid confidence is corrected UPWARD too


def test_retrospective_self_assessment_is_not_scoreable(store):
    """L1.29(a): a probability without a pre-committed resolve_by was graded AFTER the fact.

    The live store held 30 such rows -- all kind=engineering, ALL outcome=1.0, resolved a median
    of 18ms after being logged. Scoring them inverted the measured bias from +0.176 (over) to
    -0.146 (under), and run_conviction_trader fed that straight into kelly_leverage."""
    for i in range(30):
        fc.log_forecast(f"eng:{i}", 0.9, "engineering")     # no resolve_by == not a forecast
        fc.resolve(f"eng:{i}", outcome=True)
    rep = fc.report()
    assert rep["n_resolved"] == 0
    assert rep["n_excluded"]["retrospective"] == 30
    assert rep["bias"] is None                              # nothing scoreable -> no correction
    assert fc.calibrated_confidence(0.44)["applied"] is False


def test_duplicate_claims_count_once(store):
    """A re-asked question is not a second observation. The probe organ re-logged one identical
    S2USDT claim 17 times in 14h at a frozen threshold; all resolve on the same print, so scoring
    them as 17 would clear the n>=5 noise gate on arithmetically ONE coin flip."""
    for i in range(17):
        fc.log_forecast(f"probe:{i}", 0.61, "calibration_probe", resolve_by=_SOON,
                        claim="Will S2USDT trade ABOVE 102.0 in 24 hours' time?")
        fc.resolve(f"probe:{i}", outcome=True)
    rep = fc.report()
    assert rep["n_resolved"] == 1                           # 17 copies == 1 observation
    assert rep["n_excluded"]["duplicate_claim"] == 16
    assert rep["bias"] is None                              # 1 < 5 -> correction still withheld


def test_inverted_bias_does_not_manufacture_edge(store):
    """The end-to-end regression: retrospective rows must never flip the SIGN of the correction.

    30 instant self-graded TRUEs alongside 5 genuine pre-registered forecasts that mostly missed.
    Pooling everything reports 'under-confident' and RAISES probabilities; only the pre-registered
    subset is scoreable, which reports 'over-confident' and shrinks them."""
    for i in range(30):
        fc.log_forecast(f"eng:{i}", 0.9, "engineering")
        fc.resolve(f"eng:{i}", outcome=True)
    for i, out in enumerate([False, False, False, True, False]):
        fc.log_forecast(f"real:{i}", 0.6, "market_direction", resolve_by=_SOON,
                        claim=f"real claim {i}")
        fc.resolve(f"real:{i}", outcome=out)
    rep = fc.report()
    assert rep["n_resolved"] == 5
    assert rep["bias"] > 0 and rep["bias_label"] == "over-confident"
    # a marginal call must be pushed AWAY from the edge boundary, never across it
    assert fc.calibrated_confidence(0.44)["adjusted"] < 0.44


def test_zero_forecasts_is_unforecasting_not_ok(store):
    import importlib
    cc = importlib.import_module("scripts.check_calibration")
    rep = cc.build_report()
    assert rep["status"] == "UNFORECASTING"           # never "OK" -- unmeasured counts as zero


# --------------------------------------------------------------------------------------------
# R0260 -- the BLIND denominator, and forecasts nobody can grade.
# --------------------------------------------------------------------------------------------

def test_numerator_is_a_subset_of_its_own_denominator(store):
    """n_resolved is drawn from `eligible`; dividing it by len(store) is a category error.

    The live shape on 2026-08-05: 42 scoreable resolved against a raw store of 172, of which 43
    rows -- retrospective, non-sizing, deduped -- can never enter the numerator. `42 < 172//4=43`
    fired BLIND; on the matched population `42 < 129//4=32` does not."""
    for i in range(30):                                   # retrospective: no resolve_by
        fc.log_forecast(f"eng:{i}", 0.9, "engineering")
        fc.resolve(f"eng:{i}", outcome=True)
    for i in range(9):                                    # non-sizing kind, excluded from report()
        fc.log_forecast(f"pass:{i}", 0.5, "discretionary_pass_backfill", resolve_by=_SOON,
                        claim=f"pass claim {i}")
        fc.resolve(f"pass:{i}", outcome=True)
    for i in range(40):                                   # genuine pre-registered, graded
        fc.log_forecast(f"real:{i}", 0.6, "market_direction", resolve_by=_SOON,
                        claim=f"real claim {i}")
        fc.resolve(f"real:{i}", outcome=i % 2 == 0)
    for i in range(90):                                   # genuine, not yet due
        fc.log_forecast(f"open:{i}", 0.6, "market_direction", resolve_by=_SOON,
                        claim=f"open claim {i}")
    rep = fc.report()
    store_rows = fc._load()["forecasts"]
    assert rep["n_resolved"] == 40
    assert rep["n_eligible"] == 130                       # 40 graded + 90 open; eng/pass excluded
    assert rep["n_eligible"] <= len(store_rows) == 169
    assert rep["n_resolved"] <= rep["n_eligible"]         # holds by construction, asserted anyway
    # The regression itself: the raw denominator fires BLIND, the matched one does not.
    assert rep["n_resolved"] < max(1, len(store_rows) // 4)      # 40 < 169//4 = 42 -> the bug
    assert rep["n_resolved"] >= max(1, rep["n_eligible"] // 4)   # 40 >= 32 -> healthy


def test_blind_reads_the_matched_population(store):
    """The fence must not fire BLIND on a desk that graded a third of everything it can grade."""
    import importlib
    for i in range(30):
        fc.log_forecast(f"eng:{i}", 0.9, "engineering")   # unscoreable ballast
        fc.resolve(f"eng:{i}", outcome=True)
    for i in range(12):
        fc.log_forecast(f"real:{i}", 0.6, "market_direction", resolve_by=_SOON,
                        claim=f"real claim {i}")
        fc.resolve(f"real:{i}", outcome=i % 2 == 0)
    for i in range(20):
        fc.log_forecast(f"open:{i}", 0.6, "market_direction", resolve_by=_SOON,
                        claim=f"open claim {i}")
    cc = importlib.import_module("scripts.check_calibration")
    rep = cc.build_report()
    assert rep["n_eligible"] == 32 and rep["n_resolved"] == 12
    assert rep["status"] != "BLIND"                       # 12/32 clears the quarter bar
    assert rep["n_resolved_raw"] == 42                    # and the raw count is published too


def test_store_with_nothing_scoreable_is_not_ok(store):
    """`n_resolved < n_eligible//4` is `0 < 0` on an empty population -- False, i.e. a PASS.

    A verdict over an empty denominator is vacuous and must never read as health (L1.57)."""
    import importlib
    for i in range(9):
        fc.log_forecast(f"eng:{i}", 0.9, "engineering")   # no resolve_by -> never scoreable
        fc.resolve(f"eng:{i}", outcome=True)
    cc = importlib.import_module("scripts.check_calibration")
    rep = cc.build_report()
    assert rep["n_eligible"] == 0
    assert rep["status"] == "UNSCOREABLE"
    assert rep["status"] not in cc._PASSING


def test_unowned_names_forecasts_no_organ_can_grade(store):
    """R0260's class defect: a deadline with no grader pins the fence the day it comes due."""
    fc.log_forecast("20260801-some-judgement-call", 0.7, "diagnosis", resolve_by=_SOON,
                    claim="repair-mode was the correct read")            # hand-logged, no owner
    fc.log_forecast("probe:x", 0.5, "calibration_probe", resolve_by=_SOON,
                    claim="Will BTCUSDT trade ABOVE 60000 in 4 hours' time?")   # organ-owned
    fc.log_forecast("20260801-declared", 0.7, "diagnosis", resolve_by=_SOON,
                    claim="unparseable but owned", resolver="scripts/run_thing.py --grade")
    fc.log_forecast("20260801-price-shaped", 0.7, "market_direction", resolve_by=_SOON,
                    claim="BTCUSDT trades above 63216.2 at +4h")         # the scorer can parse it
    from scripts.score_forecasts import auto_resolvable
    keys = [u["key"] for u in fc.unowned(auto_resolvable, root=Path("."))]
    assert keys == ["20260801-some-judgement-call"]


def test_unowned_flags_a_namespace_whose_resolver_was_deleted(store, tmp_path):
    """Reachability, not declaration: the map names a script, and the script must still exist."""
    fc.log_forecast("probe:x", 0.5, "calibration_probe", resolve_by=_SOON, claim="judgement call")
    assert fc.unowned(root=Path(".")) == []               # scripts/run_calibration_probe.py exists
    orphans = fc.unowned(root=tmp_path)                   # same store, resolver not on disk
    assert [o["key"] for o in orphans] == ["probe:x"]
    assert "MISSING" in orphans[0]["why"]


def test_a_keyless_namespace_can_never_be_rescued_by_ORGAN_RESOLVERS(store):
    """R0422. Every unowned test above uses an `orphan:x` key WITH a colon, so all of them
    exercise the ORGAN_RESOLVERS branch -- and all 13 real orphans had NO colon at all.

    With no colon `ns` is "" and `ORGAN_RESOLVERS.get("")` is None forever, so adding entries to
    that map can never own these rows however many are added. A declared `resolver=` is the ONLY
    escape, which is why the fix was 13 per-row backfills and not a new namespace.
    """
    fc.log_forecast("20260801-no-namespace-at-all", 0.7, "diagnosis", resolve_by=_SOON,
                    claim="a judgement call in prose")
    assert [u["key"] for u in fc.unowned(root=Path("."))] == ["20260801-no-namespace-at-all"]
    assert "no organ owns this namespace" in fc.unowned(root=Path("."))[0]["why"]
    # ...and the ONLY thing that clears it is naming a grader.
    fc.log_forecast("20260801-no-namespace-at-all", 0.7, "diagnosis",
                    resolver="data/some_artifact.json: field x > y")
    assert fc.unowned(root=Path(".")) == []


def test_a_row_with_no_claim_is_voidable_rather_than_gradeable(store):
    """R0422's worst-shaped row: p, kind and a deadline, but no `claim` -- so there is no
    recorded statement of what was predicted. Reconstructing one and grading it would fabricate
    an outcome into the term that feeds calibrated_confidence and Kelly."""
    fc.log_forecast("20260731-claimless", 0.7, "fence-yield", resolve_by=_SOON)
    assert fc.unowned(root=Path("."))[0]["claim"] == ""
    assert fc.void("20260731-claimless", "no claim was ever recorded -- nothing to grade")
    assert fc.unowned(root=Path(".")) == []
    assert fc.get_forecast("20260731-claimless").get("resolved") is None   # voided != scored


def test_resolved_rows_are_never_unowned(store):
    fc.log_forecast("20260801-graded", 0.7, "diagnosis", resolve_by=_SOON, claim="a judgement")
    assert len(fc.unowned(root=Path("."))) == 1
    fc.resolve("20260801-graded", outcome=True)
    assert fc.unowned(root=Path(".")) == []


def test_law_and_wiring_present():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.29 THE DESK SCORES ITS OWN CONFIDENCE" in const
    assert "L1.29" in Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert '"L1.29"' in Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert "check_calibration.py" in Path("ops/crontab.manifest").read_text("utf-8")
    assert "calibration_debt" in Path("scripts/run_max_push.py").read_text("utf-8")
