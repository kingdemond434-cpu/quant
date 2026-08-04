"""HYPOTHESIS_MAX_SPEC components 1, 3 and 6 -- built 2026-07-29, spec'd 2026-07-20.

The tests that matter here are the ones pinning the spec's INVERTED default. Everywhere else on
this desk an ambiguous branch must block; in a discovery pre-filter it must not, because the
failure mode is a silently killed alpha rather than a bad trade. Getting that direction wrong
would turn a compute optimisation into the thing that decides what the desk is allowed to find,
and it would look exactly like correct fail-closed discipline while doing it.
"""

from __future__ import annotations

import math

import pytest

from libs.hypmax.hypothesis_max import (
    COST_FLOOR_MULTIPLE,
    MIN_FAMILY_WEIGHT,
    TrivialVariationBlocker,
    batch_diversity,
    family_weight,
    fingerprint,
    horizon_bucket,
    prefilter,
)

# --------------------------------------------------------------------------- #3 fingerprint


def test_parameter_tweaks_collapse_to_one_fingerprint() -> None:
    """The blocker is worthless if a parameter change mints a new mechanism."""
    a = fingerprint("rsi", "zscore", 12.0)
    assert a == fingerprint("rsi_14", "zscore", 13.0)
    assert a == fingerprint("RSI 21", "z-score", 20.0)


def test_a_real_mechanism_change_is_a_different_fingerprint() -> None:
    base = fingerprint("rsi", "zscore", 12.0)
    assert fingerprint("funding", "zscore", 12.0) != base, "different feature family"
    assert fingerprint("rsi", "rank", 12.0) != base, "different transform"
    assert fingerprint("rsi", "zscore", 400.0) != base, "different horizon regime"


@pytest.mark.parametrize(("hours", "bucket"), [
    (0.5, "micro"), (1.0, "intraday"), (6.0, "session"),
    (24.0, "swing"), (100.0, "position"), (1000.0, "carry"),
])
def test_horizon_buckets(hours: float, bucket: str) -> None:
    assert horizon_bucket(hours) == bucket


def test_nonsense_horizons_do_not_crash() -> None:
    for bad in (0.0, -5.0, math.nan, math.inf):
        assert horizon_bucket(bad) in {"unknown", "carry"}


# --------------------------------------------------------------------------- #1 pre-filter


def test_absence_of_evidence_escalates_and_never_rejects() -> None:
    """THE CENTRAL RULE. A candidate nobody measured must reach the full gauntlet."""
    v = prefilter(feature_family="depth", transform="slope", horizon_h=4.0)
    assert v.decision == "ESCALATE"
    assert v.proceeds


def test_borderline_statistics_escalate() -> None:
    """Thresholds sit far below any promotion bar: this stage removes the hopeless only."""
    v = prefilter(feature_family="funding", transform="zscore", horizon_h=8.0,
                  t_stat=1.4, ic=0.02, sign_stability=0.55)
    assert v.decision == "PASS"
    assert v.proceeds


def test_hopeless_statistics_reject() -> None:
    v = prefilter(feature_family="noise", transform="raw", horizon_h=8.0,
                  t_stat=0.11, ic=0.0004, sign_stability=0.2)
    assert v.decision == "REJECT"
    assert len(v.reasons) == 3


def test_cost_floor_rejects_an_edge_that_cannot_pay_for_itself() -> None:
    v = prefilter(feature_family="microprice", transform="diff", horizon_h=2.0,
                  gross_edge_bps=3.0, round_trip_cost_bps=2.0, t_stat=4.0)
    assert v.decision == "REJECT"
    assert "cost floor" in v.reasons[0]

    ok = prefilter(feature_family="microprice", transform="diff", horizon_h=2.0,
                   gross_edge_bps=2.0 * COST_FLOOR_MULTIPLE + 0.1,
                   round_trip_cost_bps=2.0, t_stat=4.0)
    assert ok.decision == "PASS"


def test_missing_cost_data_cannot_cause_a_rejection() -> None:
    """Half the cost pair present is not evidence -- it is a missing cost model."""
    v = prefilter(feature_family="microprice", transform="diff", horizon_h=2.0,
                  gross_edge_bps=0.01, round_trip_cost_bps=None, t_stat=3.0)
    assert v.decision == "PASS"


def test_degenerate_turnover_rejects_both_directions() -> None:
    assert prefilter(feature_family="f", transform="t", horizon_h=4.0,
                     turnover=0.0).decision == "REJECT"
    assert prefilter(feature_family="f", transform="t", horizon_h=4.0,
                     turnover=999.0).decision == "REJECT"


def test_prefilter_rejects_a_blocked_trivial_variation_before_any_maths() -> None:
    b = TrivialVariationBlocker()
    b.block("rsi", "zscore", 12.0, "M_PRICE_PATTERN family kill")
    v = prefilter(feature_family="rsi_9", transform="z-score", horizon_h=14.0,
                  t_stat=9.9, ic=0.5, blocker=b)
    assert v.decision == "REJECT"
    assert "trivial variation" in v.reasons[0]
    assert "M_PRICE_PATTERN" in v.reasons[0]


def test_a_new_mechanism_is_not_blocked_by_a_sibling_rejection() -> None:
    b = TrivialVariationBlocker()
    b.block("rsi", "zscore", 12.0, "dead")
    v = prefilter(feature_family="orderbook_depth", transform="zscore", horizon_h=12.0,
                  t_stat=3.0, blocker=b)
    assert v.decision == "PASS"


def test_blocking_is_reversible() -> None:
    """Charter s18 -- negative knowledge is reversible, so the blocklist needs an exit."""
    b = TrivialVariationBlocker()
    fp = b.block("rsi", "zscore", 12.0, "dead")
    assert len(b) == 1 and b.is_blocked(fp)
    assert b.unblock(fp) is True
    assert not b.is_blocked(fp) and len(b) == 0
    assert b.unblock(fp) is False


# --------------------------------------------------------------------------- #2 weighting


def test_dead_family_is_demoted_but_never_silenced() -> None:
    """A zero weight is self-sealing: never proposed, so never revived."""
    w = family_weight(rejections=100, total=100)
    assert w == MIN_FAMILY_WEIGHT
    assert w > 0.0
    assert family_weight(0, 10) == 1.0
    assert family_weight(5, 10) == pytest.approx(0.5)
    assert family_weight(0, 0) == 1.0


# --------------------------------------------------------------------------- #6 collapse


def test_collapse_detected_when_entropy_falls_while_volume_holds() -> None:
    names = ["funding", "depth", "basis", "oi", "skew", "carry",
             "flow", "vol", "spread", "imbalance", "premium", "liquidation"]
    diverse = [fingerprint(n, "z", 4.0) for n in names]
    d1 = batch_diversity(diverse)
    assert not d1.collapsed and d1.normalised == pytest.approx(1.0)

    # Same batch SIZE, nearly all one mechanism -- the exact failure mode.
    collapsed = [fingerprint("funding", "z", 4.0)] * 11 + [fingerprint("depth", "z", 4.0)]
    d2 = batch_diversity(collapsed, prior_normalised=d1.normalised)
    assert d2.n == d1.n, "volume must be held constant or this proves nothing"
    assert d2.collapsed
    assert any("duplicate rate" in r for r in d2.reasons)


def test_normalised_entropy_is_what_gets_compared_across_batches() -> None:
    """Raw entropy rises with batch size; comparing it would call a bigger batch a better one."""
    def _names(k):  # letters only -- digit suffixes collapse by design
        import itertools
        import string
        return ["".join(c) for c in itertools.islice(
            itertools.product(string.ascii_lowercase, repeat=2), k)]
    small = batch_diversity([fingerprint(n, "z", 4.0) for n in _names(4)])
    big = batch_diversity([fingerprint(n, "z", 4.0) for n in _names(64)])
    assert big.entropy > small.entropy
    assert big.normalised == pytest.approx(small.normalised)
    assert not big.collapsed and not small.collapsed


def test_duplicate_rate_alone_trips_collapse_with_no_prior_batch() -> None:
    """The first batch has nothing to compare against and must still be judgeable."""
    d = batch_diversity([fingerprint("same", "z", 4.0)] * 8 + [fingerprint("other", "z", 4.0)])
    assert d.collapsed and d.duplicate_rate > 0.25


def test_empty_batch_is_not_a_collapse() -> None:
    d = batch_diversity([])
    assert not d.collapsed and d.n == 0


def test_module_stays_dependency_free() -> None:
    """The pre-filter exists to be cheap. A multi-second import would defeat its purpose."""
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys;import libs.hypmax.hypothesis_max as m;"
         "print(sorted({x.split('.')[0] for x in sys.modules} & "
         "{'duckdb','pandas','scipy','numpy','pydantic'}))"],
        capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.strip() == "[]", f"heavy imports leaked in: {r.stdout}"
