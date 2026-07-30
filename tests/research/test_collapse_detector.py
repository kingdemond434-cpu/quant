"""Collapse must be visible in the metric, and a healthy batch must not trip it.

The failure this instruments: multiple seats converging on near-identical hypotheses, so THROUGHPUT
rises while INFORMATION throughput falls. Every dashboard the desk owns counts candidates, so
collapse reads as productivity -- "420 tests" and "one question asked 420 ways" are identical from
a count. These pin that the detector separates them, and that it stays quiet on a diverse batch,
because a detector that fires on healthy work is muted long before it sees a real collapse.
"""

from __future__ import annotations

import pytest

from libs.research import collapse_detector as CD
from libs.research.mechanism_fingerprint import fingerprint, horizon_bucket, signal_transform


class _H:
    """Minimal hypothesis stand-in: the detector reads attributes, not a pydantic model."""

    def __init__(self, family="carry", subtype="funding_carry", symbol="BTCUSDT",
                 edge_source="funding/carry", mechanism="risk_premium", params=None,
                 failure_modes=()):
        self.family, self.subtype, self.symbol = family, subtype, symbol
        self.edge_source, self.mechanism = edge_source, mechanism
        self.params = params or {"horizon_days": 7}
        self.failure_modes = list(failure_modes)


def _collapsed(n=20):
    """n hypotheses that are ONE idea with different parameters -- the exact failure mode."""
    return [_H(params={"horizon_days": 7, "threshold": 0.1 * i}) for i in range(n)]


def _diverse(n=20):
    fams = ["carry", "flow", "vol", "reversal", "spread"]
    subs = ["funding_carry", "netflow_momentum", "vol_dispersion", "mean_revert", "basis_spread"]
    horizons = [1, 5, 21, 63, 252]
    return [_H(family=fams[i % 5], subtype=subs[i % 5], symbol=f"SYM{i}",
               edge_source=f"{fams[i % 5]}/{subs[i % 5]}",
               params={"horizon_days": horizons[(i // 5) % 5]}) for i in range(n)]


class TestCollapseIsVisible:
    def test_reparameterised_batch_scores_far_below_a_diverse_one(self):
        col, div = CD.measure(_collapsed()), CD.measure(_diverse())
        assert col.n == div.n, "same VOLUME -- which is the whole point"
        assert col.mechanism_entropy < 0.3
        assert div.mechanism_entropy > col.mechanism_entropy * 2

    def test_a_collapsed_batch_has_one_fingerprint(self):
        assert CD.measure(_collapsed()).n_fingerprints == 1

    def test_entropy_is_normalised_by_ITEMS_not_categories(self):
        """The subtle one. Normalising by log(n_categories) reports 50 ideas sharing 2 fingerprints
        as PERFECTLY diverse -- both categories equally used, entropy 1.0. Against log(n_items) the
        same batch reads ~0.18, which is what actually happened."""
        two = [_H(subtype="funding_carry") for _ in range(25)] + \
              [_H(family="vol", subtype="vol_dispersion", edge_source="vol/dispersion")
               for _ in range(25)]
        d = CD.measure(two)
        assert d.n_fingerprints == 2
        assert d.mechanism_entropy < 0.25, (
            f"two fingerprints across 50 ideas must not read as diverse (got "
            f"{d.mechanism_entropy})")

    def test_semantic_distinctness_separates_the_two(self):
        assert CD.measure(_collapsed()).semantic_distinctness < \
               CD.measure(_diverse()).semantic_distinctness


class TestMarketBreadthCountsTheUniverse:
    def test_a_cross_sectional_idea_is_not_scored_as_a_single_name(self):
        """Counting `symbol` alone scores the BROADEST idea as the narrowest, inverting the
        measure. A cross-sectional signal ranks a universe."""
        single = CD.measure([_H(symbol="BTCUSDT")] * 4)
        xs = CD.measure([_H(subtype="rank_xs", params={"horizon_days": 7,
                                                       "cross_sectional": True,
                                                       "universe_size": 200})] * 4)
        assert single.market_breadth == 1
        assert xs.market_breadth == 200

    def test_explicit_universe_is_honoured(self):
        h = _H()
        h.universe = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        assert CD.measure([h]).market_breadth == 3


class TestCrossGeneratorHerding:
    def test_two_seats_producing_the_same_idea_is_flagged(self):
        batch = _collapsed(10)
        gens = ["seat_a"] * 5 + ["seat_b"] * 5
        d = CD.measure(batch, generators=gens)
        assert d.cross_generator_dup_rate > CD.CROSS_DUP_TRIGGER
        assert CD.assess(d)["verdict"] == "DIVERSITY-AUDIT"

    def test_independent_seats_on_distinct_ideas_are_not_flagged(self):
        batch = _diverse(10)
        d = CD.measure(batch, generators=["seat_a"] * 5 + ["seat_b"] * 5)
        assert d.cross_generator_dup_rate <= CD.CROSS_DUP_TRIGGER

    def test_dup_rate_is_zero_without_generator_labels(self):
        """Unlabelled batches must not fabricate a cross-generator reading."""
        assert CD.measure(_collapsed()).cross_generator_dup_rate == 0.0


class TestTheTrailingComparison:
    def test_a_drop_below_the_trailing_median_flags_an_audit(self, tmp_path):
        p = tmp_path / "hist.jsonl"
        for _ in range(5):
            CD.record(CD.measure(_diverse()), path=p)
        out = CD.assess(CD.measure(_collapsed()), path=p)
        assert out["verdict"] == "DIVERSITY-AUDIT"
        assert any("mechanism_entropy" in f for f in out["flags"])

    def test_a_healthy_batch_after_healthy_history_stays_quiet(self, tmp_path):
        p = tmp_path / "hist.jsonl"
        for _ in range(5):
            CD.record(CD.measure(_diverse()), path=p)
        assert CD.assess(CD.measure(_diverse()), path=p)["verdict"] == "OK"

    def test_too_little_history_does_not_flag(self, tmp_path):
        """Fewer than 3 prior batches is not a median. Firing on 1-2 observations is the same
        n=2 superstition check_mine_evidence_base exists to prevent."""
        p = tmp_path / "hist.jsonl"
        CD.record(CD.measure(_diverse()), path=p)
        assert CD.assess(CD.measure(_collapsed()), path=p)["verdict"] == "OK"

    def test_a_tiny_batch_is_under_sampled_not_collapsed(self, tmp_path):
        out = CD.assess(CD.measure(_collapsed(3)), path=tmp_path / "hist.jsonl")
        assert out["verdict"] == "UNDER-SAMPLED"
        assert out["flags"] == []


def test_it_never_blocks_generation():
    """The spec is explicit: instrumentation that pages the process, not a gate on ideas. A
    diversity metric with veto power is a second unvalidated filter on the discovery funnel."""
    import inspect
    src = inspect.getsource(CD)
    assert "raise" not in src.split('"""')[-1], "the detector must not raise on a collapsed batch"
    out = CD.assess(CD.measure(_collapsed()))
    assert out["verdict"] in {"OK", "DIVERSITY-AUDIT", "UNDER-SAMPLED"}
    assert "never a gate" in out["note"]


class TestFingerprint:
    @pytest.mark.parametrize(("days", "bucket"), [
        (None, "unspecified"), (0.5, "intraday"), (1, "intraday"), (5, "days"),
        (20, "weeks"), (21, "weeks"), (30, "months"), (252, "quarters"), (500, "annual+"),
    ])
    def test_horizon_bucketing_is_coarse_on_purpose(self, days, bucket):
        assert horizon_bucket(days) == bucket

    def test_20_and_21_day_lookbacks_are_the_same_idea(self):
        a = _H(params={"horizon_days": 20})
        b = _H(params={"horizon_days": 21})
        assert fingerprint(a) == fingerprint(b), (
            "treating a lookback tweak as a new hypothesis is the forking-paths failure this "
            "fingerprint exists to collapse")

    def test_the_same_mechanism_on_two_symbols_is_one_idea(self):
        assert fingerprint(_H(symbol="BTCUSDT")) == fingerprint(_H(symbol="ETHUSDT"))

    def test_transforms_are_recognised(self):
        assert signal_transform("cross-sectional rank of funding") == "rank"
        assert signal_transform("basis spread dislocation") == "carry"   # carry ranks before spread
        assert signal_transform("something with no known shape") == "unclassified"
